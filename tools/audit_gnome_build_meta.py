#!/usr/bin/env python3
"""Deterministic audit of GNOME RPM recipes against GNOME/gnome-build-meta.

This factory inherits Fedora RPM recipes, but GNOME release integration is
defined upstream in `GNOME/gnome-build-meta` (BuildStream). Without a repeatable
comparison, drift is invisible: source version/commit can leave the intended
GNOME release line, GNOME carries secondary sources / wraps / patches the RPM
recipe handles differently, Meson feature choices diverge, dependency edges
differ, and the package set can drift from GNOME core/sdk membership.

This tool makes that delta explicit and classified. It is an AUDIT, not a
mechanism to replace Fedora packaging: Fedora integration, Hummingbird
constraints, RPM subpackages and downstream policy can all justify a
difference. The goal is a maintained, evidence-backed delta, not a one-time
spreadsheet.

Inputs
------
- ``config/gnome-build-meta.json``   pinned GNOME release (tag + commit) and the
  explicit source-name mapping (RPM name -> gbm element path).
- ``config/upstream-sources.json``   the factory source locks (identity /
  version / filename / sha512), consistent with the factory contract.
- ``packages/<name>/<name>.spec``    the Fedora recipe (version, Source0,
  patches, feature options, dependency edges).
- ``--gbm-dir``                      a checkout of gnome-build-meta at the pinned
  commit. If it is a git repository the tool verifies the working tree resolves
  to the pinned commit (unless ``--no-verify``) so a mutable checkout cannot be
  silently compared against.

Outputs
-------
- machine-readable JSON (``--json-out``) and a human reviewable Markdown
  summary (``--markdown-out``). Every difference is classified, and the raw
  evidence (source identity, release line, patches, feature options,
  dependency categories, component membership) is preserved for review.

Only the Python standard library plus PyYAML is required, so it runs on a
GitHub-hosted runner and in the digest-pinned factory images without installing
extra runtime tooling.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
import subprocess

import yaml

# --- Classification vocabulary -------------------------------------------------
ALIGNED = "aligned"
INTENTIONAL_FEDORA = "intentional_fedora"
INTENTIONAL_HUMMINGBIRD = "intentional_hummingbird"
ACTIONABLE = "actionable_drift"
NEEDS_REVIEW = "needs_review"
UNMAPPED = "unmapped"

# BuildStream merge/overlay operators that we record but do not fully resolve.
_BST_EXTENSIONS = ("(>)", "(<)", "(=)", "(^)", "(/)", "(~)")

_VERSION_LINE_RE = re.compile(r"(\d+)\.(\d+)")


def numeric_components(version: str) -> list[str]:
    """Leading numeric components of a version string (``51.beta`` -> ``["51"]``)."""
    if not version:
        return []
    return re.findall(r"\d+", version)


def release_line(version: str) -> str | None:
    """The release line of a GNOME-style version.

    GNOME switched to consecutive single-number cycles at 40 (``51.0``,
    ``51.beta`` -> ``51``); libraries keep ``major.minor`` lines (``4.23``,
    ``1.10``, ``2.62``, ``3.12``...). A version whose major is >= 40 is treated
    as a GNOME-cycle number; anything smaller as a library line.
    """
    digits = numeric_components(version)
    if not digits:
        return None
    if int(digits[0]) >= 40:
        return digits[0]
    if len(digits) >= 2:
        return f"{digits[0]}.{digits[1]}"
    return digits[0]


def same_release_line(version_a: str, version_b: str) -> bool:
    """True when two versions share a release line (see ``release_line``)."""
    a = release_line(version_a)
    b = release_line(version_b)
    return bool(a) and a == b


@dataclass
class Element:
    """A resolved gbm BuildStream element, normalized for comparison."""

    path: str
    kind: str | None
    sources: list[dict]
    variables: dict
    build_depends: list[str]
    runtime_depends: list[str]
    depends: list[str]
    includes: list[str]
    extensions: list[str]
    primary_source: dict | None


class Loader:
    """Resolve BuildStream ``(@)`` includes into a normalized element.

    BuildStream ``(@)`` handles includes deliberately; a regex-only scan that
    ignores included variables or dependency composition is explicitly not a
    sufficient audit. This loader:

    - splices ``- (@): path`` list items (splicing list-form includes into the
      list; dict-form includes such as ``include/gcc-for-recc.yml`` are recorded
      but not treated as dependency entries, because they carry compiler
      configuration rather than element references);
    - opens mapping-level ``(@): path|list`` includes and deep-merges them;
    - records every resolved include and every unresolved BuildStream merge
      operator (``(>)``, ``(<)``, ...) so the report states exactly what was and
      was not expanded.
    """

    def __init__(self, root: Path):
        self.root = root                       # repository root of the checkout
        self.seen: set[str] = set()            # include files resolved (repo-relative)

    def _resolve_path(self, raw: str, current: Path) -> Path:
        # BuildStream include paths are repo-relative: both `include/x.yml` and
        # `elements/core/foo.inc` resolve against the repository root, never
        # against the including element's directory.
        target = Path(raw)
        if target.is_absolute():
            return self.root / str(target).lstrip("/")
        return self.root / target

    def load(self, relpath: str) -> dict:
        """Load and fully resolve one element file (repo-relative path)."""
        path = self.root / relpath
        node = self._file(path)
        return node

    def _file(self, path: Path) -> dict:
        node = yaml.safe_load(path.read_text())
        if not isinstance(node, dict):
            return node if node is not None else {}
        return self._node(node, path)

    def _merge(self, base: dict, over: dict) -> dict:
        """Shallow/deep merge; ``(>)`` keys in ``over`` win (BuildStream override)."""
        out = dict(base)
        for key, value in over.items():
            if key == "(>)" or key.startswith("(>"):
                continue
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = self._merge(out[key], value)
            else:
                out[key] = value
        return out

    def _open_include(self, raw: str, current: Path) -> dict:
        p = self._resolve_path(raw, current)
        self._note_include(p)
        return self._file(p)

    def _note_include(self, path: Path) -> None:
        try:
            self.seen.add(str(path.relative_to(self.root)))
        except ValueError:
            self.seen.add(str(path))

    def _node(self, node: dict, path: Path) -> dict:
        node = dict(node)

        # Mapping-level `(@):` open include: value is a path or list of paths.
        inc = node.pop("(@)", None)
        if inc is not None:
            items = inc if isinstance(inc, list) else [inc]
            merged: dict = {}
            for raw in items:
                part = self._open_include(raw, path)
                merged = self._merge(merged, part)
            node = self._merge(merged, node)

        for key, value in list(node.items()):
            if key in _BST_EXTENSIONS:
                continue
            if isinstance(value, dict):
                node[key] = self._node(value, path)
            elif isinstance(value, list):
                node[key] = self._list(value, path)
        return node

    def _list(self, items: list, path: Path) -> list:
        out: list = []
        for item in items:
            if isinstance(item, dict) and "(@)" in item:
                raw = item["(@)"]
                p = self._resolve_path(raw, path)
                self._note_include(p)
                loaded = self._file(p)
                if isinstance(loaded, list):
                    out.extend(loaded)
                # dict-form include (e.g. gcc-for-recc.yml) resolved elsewhere;
                # not a dependency entry.
                continue
            if isinstance(item, dict):
                out.append(self._node(item, path))
            else:
                out.append(item)
        return out


def _expand_alias(url: str, aliases: dict) -> str:
    """Expand a ``gnome_downloads:module/...`` source url using aliases.yml."""
    if ":" not in url:
        return url
    alias, _, rest = url.partition(":")
    base = aliases.get(alias)
    if base is None:
        return url
    return base.rstrip("/") + "/" + rest.lstrip("/")


def _aliases(loader: Loader) -> dict:
    p = loader.root / "include" / "aliases.yml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    return data.get("aliases", {}) if isinstance(data, dict) else {}


def resolve_element(loader: Loader, aliases: dict, relpath: str) -> Element:
    node = loader.load(relpath)
    bs = node.get("bst") or {}
    depends = node.get("depends", []) or []
    build_depends = node.get("build-depends", []) or []
    runtime_depends = node.get("runtime-depends", []) or []

    def refs(items: list) -> list[str]:
        return [i for i in items if isinstance(i, str) and i.endswith(".bst")]

    sources = node.get("sources", []) or []
    if not isinstance(sources, list):
        sources = []
    variables = node.get("variables", {}) or {}
    if not isinstance(variables, dict):
        variables = {}

    # collect extension operators that reached this element node
    extensions = sorted(_collect_extensions(node))

    primary = None
    for source in sources:
        if source.get("kind") != "patch" and source.get("url"):
            primary = {
                "kind": source.get("kind"),
                "url": _expand_alias(str(source.get("url")), aliases),
                "ref": source.get("ref"),
                "directory": source.get("directory") or source.get("subdir"),
                "track": source.get("track"),
            }
            break

    return Element(
        path=relpath,
        kind=node.get("kind"),
        sources=sources,
        variables=variables,
        build_depends=refs(build_depends),
        runtime_depends=refs(runtime_depends),
        depends=refs(depends),
        includes=sorted(loader.seen),
        extensions=extensions,
        primary_source=primary,
    )


def _collect_extensions(node: dict) -> set[str]:
    found: set[str] = set()
    for key, value in node.items():
        if key in _BST_EXTENSIONS:
            found.add(key)
        if isinstance(value, dict):
            found |= _collect_extensions(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found |= _collect_extensions(item)
    return found


def element_patch_sources(element: Element, aliases: dict) -> list[str]:
    """Patch sources (kind: patch / patch local path) carried by the element."""
    patches = []
    for source in element.sources:
        if source.get("kind") == "patch":
            local = source.get("local") or source.get("url") or ""
            patches.append(_expand_alias(str(local), aliases))
    return patches


def meson_options(text: str) -> dict[str, str]:
    """Extract Meson ``-Dname=value`` options from spec text (any line).

    Fedora GNOME specs spread Meson options across ``%meson \\`` continuation
    lines, so the whole file is scanned, not just the ``%meson`` directive.
    """
    out: dict[str, str] = {}
    for token in re.findall(r"-D([^\s]+)", text):
        token = token.rstrip("\\").strip()
        if "=" in token:
            name, _, value = token.partition("=")
        else:
            name, value = token, ""
        name = name.strip("-").strip()
        value = value.strip().strip("'\"")
        if name and name not in out:
            out[name] = value
    return out


def spec_patches(text: str) -> list[str]:
    """Patch references in a Fedora spec (``Patch:`` / ``PatchN:`` lines)."""
    patches = []
    for m in re.finditer(r"^Patch\d*\s*:\s*(\S+)", text, flags=re.MULTILINE):
        patches.append(m.group(1))
    return patches


def spec_sources(text: str) -> list[str]:
    """Source tarball references (``Source``/``Source0:``... lines)."""
    sources = []
    for m in re.finditer(r"^Source\w*\s*:\s*(\S+)", text, flags=re.MULTILINE):
        sources.append(m.group(1).strip())
    return sources


def factory_package(sources: dict, name: str) -> dict | None:
    return sources.get(name)


def _gbm_module(primary: dict) -> str | None:
    """The GNOME module name a primary source belongs to.

    download.gnome.org URLs are ``/sources/<module>/<line>/<file>``; git URLs
    carry the repo name in the final path segment.
    """
    url = primary.get("url") or ""
    m = re.search(r"/sources/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.search(r"/([^/]+?)\.git/?$", url)
    if m:
        return m.group(1)
    return None


def _rpm_base_name(name: str) -> str:
    """RPM name with a trailing subpackage/version digit(s) stripped.

    Fedora names ``gnome-desktop3``, ``gdk-pixbuf2``, ``gtk3``, ``librsvg2``
    for GNOME modules named ``gnome-desktop``, ``gdk-pixbuf``, ``gtk``,
    ``librsvg``.
    """
    return re.sub(r"\d+$", "", name).lower()


def _gbm_version(primary: dict) -> str | None:
    """The version encoded in a gbm tar source url."""
    m = re.search(r"-(\d[\w.~-]*)\.tar(?:\.(?:gz|bz2|xz|zst))?$", primary.get("url", "") or "")
    if m:
        return m.group(1)
    return None


def classify(gbm: Element | None, factory: dict | None, factory_version: str | None,
             notes: list[str]) -> tuple[str, str]:
    """Classify the difference for one mapped source.

    Returns ``(classification, reason)``. The classifier is deliberately
    conservative: it marks *aligned* only when there is no material drift
    evidence, and otherwise returns ``needs_review`` with concrete notes so a
    human can re-classify as intentional Fedora/Hummingbird policy.
    """
    if gbm is None:
        return UNMAPPED, "no gnome-build-meta element in the pinned tree"
    if factory is None:
        return UNMAPPED, "factory source not present in config/upstream-sources.json"
    if not gbm.sources:
        if gbm.kind in ("filter", "stack", "compose"):
            return ALIGNED, (
                f"gbm element is an {gbm.kind} aggregating shared sources; "
                "membership aligned (no independent source identity to compare)"
            )
        return NEEDS_REVIEW, "element present but has no analysable sources"

    primary = gbm.primary_source
    if primary is None:
        return NEEDS_REVIEW, "gnome-build-meta element has no analysable primary source"

    gbm_version = _gbm_version(primary)
    gbm_module = _gbm_module(primary)
    src_name = factory.get("name", "")

    drift: list[str] = []
    info: list[str] = []

    # Source identity: same GNOME module on both sides.
    if gbm_module and src_name:
        if _rpm_base_name(src_name) != gbm_module.lower():
            drift.append(
                f"factory module '{src_name}' (base '{_rpm_base_name(src_name)}') "
                f"vs gbm module '{gbm_module}'"
            )

    # Release line comparison (factory is usually the rawhide/dev line).
    if gbm_version and factory_version:
        if same_release_line(gbm_version, factory_version):
            if gbm_version != factory_version:
                info.append(
                    f"release line {release_line(gbm_version)} matches; factory "
                    f"{factory_version} vs gbm {gbm_version} (factory tracks the "
                    f"dev/rawhide bump within the same line)"
                )
        else:
            drift.append(
                f"release line {release_line(factory_version)} (factory) vs "
                f"{release_line(gbm_version)} (gbm)"
            )

    gbm_patch_list = element_patch_sources(gbm, {})
    spec_patch_list = factory.get("patches", [])
    if spec_patch_list and not gbm_patch_list:
        drift.append(f"factory carries {len(spec_patch_list)} local patch(es); gbm none")
    if gbm_patch_list and not spec_patch_list:
        drift.append("gbm carries upstream patches; factory spec has none")

    if drift:
        return NEEDS_REVIEW, "; ".join(drift)
    return ALIGNED, "; ".join(info) if info else "source identity and release line aligned"


def build_report(pin: dict, loader: Loader, aliases: dict,
                 factory_sources: dict, packages_dir: Path) -> dict:
    mapping = pin["mapping"]
    alias = pin.get("factory_alias", {}) or {}
    entries = []
    for rpm, elem_path in mapping.items():
        # Subpackages (gvfs-client, gvfs-daemon) and rename aliases (tinysparql)
        # resolve to a real factory source registry name.
        factory_name = alias.get(rpm, rpm)
        pkg = factory_sources.get(factory_name)
        notes: list[str] = []
        if factory_name != rpm and pkg is None:
            notes.append(f"factory alias '{rpm}' -> '{factory_name}' has no registry entry")

        elem_path_full = pin["element_path"]["root"] + "/" + elem_path
        gbm = None
        if (loader.root / elem_path_full).exists():
            try:
                gbm = resolve_element(loader, aliases, elem_path_full)
            except Exception as exc:  # noqa: BLE001 - report, never abort the audit
                notes.append(f"gbm element failed to parse: {exc}")
        else:
            notes.append(f"mapped element '{elem_path}' not found in gnome-build-meta")

        factory_version = None
        factory_spec = {}
        if pkg:
            factory_version = pkg.get("version")
            spec_name = pkg.get("spec", f"{factory_name}.spec")
            spec_path = packages_dir / factory_name / spec_name
            if spec_path.exists():
                spec_text = spec_path.read_text()
                factory_spec = {
                    "sources": spec_sources(spec_text),
                    "patches": spec_patches(spec_text),
                    "meson_options": meson_options(spec_text),
                    "version": factory_version,
                }
            else:
                factory_spec = {"version": factory_version, "meson_options": {}}
                notes.append(f"no spec file found at {spec_path}")

        classify_factory = dict(pkg) if pkg else None
        if classify_factory is not None:
            classify_factory["patches"] = factory_spec.get("patches", [])
        classification, reason = classify(gbm, classify_factory, factory_version, list(notes))

        entry = {
            "rpm_name": rpm,
            "gbm_element": elem_path,
            "gbm_present": gbm is not None,
            "classification": classification,
            "reason": reason,
            "factory": {
                "name": pkg.get("name") if pkg else None,
                "version": factory_version,
                "filename": pkg.get("filename") if pkg else None,
                "patches": factory_spec.get("patches", []),
                "features": factory_spec.get("meson_options", {}),
                "source_urls": factory_spec.get("sources", []),
            },
            "gnome_build_meta": {
                "kind": gbm.kind if gbm else None,
                "primary_source": gbm.primary_source if gbm else None,
                "secondary_sources": _secondary_sources(gbm, aliases),
                "patches": element_patch_sources(gbm, aliases) if gbm else [],
                "features": gbm.variables if gbm else {},
                "build_depends": gbm.build_depends if gbm else [],
                "runtime_depends": gbm.runtime_depends if gbm else [],
                "depends": gbm.depends if gbm else [],
                "includes": gbm.includes if gbm else [],
                "extensions": gbm.extensions if gbm else [],
            },
        }
        entries.append(entry)

    return {
        "schema": 1,
        "generated_for": {
            "release_tag": pin["source"]["release_tag"],
            "release_commit": pin["source"]["release_commit"],
            "factory_base": _factory_rev(),
        },
        "unmapped_factory_sources": _unmapped_observed(pin, factory_sources),
        "packages": entries,
    }


def _secondary_sources(gbm: Element | None, aliases: dict) -> list[dict]:
    """Element sources other than the primary (secondary sources, wraps)."""
    if gbm is None:
        return []
    primary = gbm.primary_source
    if primary is None:
        return []
    primary_expanded = primary.get("url")
    out = []
    for source in gbm.sources:
        if _expand_alias(str(source.get("url", "")), aliases) == primary_expanded:
            continue
        out.append(source)
    return out


def _unmapped_observed(pin: dict, factory_sources: dict) -> list[dict]:
    """GNOME-owned factory sources the mapping deliberately does not track."""
    return [dict(u) for u in pin.get("unmapped", [])]


def _factory_rev() -> str:
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        return rev or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _load_factory_sources(path: Path) -> dict:
    data = json.loads(path.read_text())
    packages = data.get("packages", [])
    return {p["name"]: p for p in packages}


def load_pin(path: Path) -> dict:
    pin = json.loads(path.read_text())
    if pin.get("schema") != 1:
        raise ValueError(f"unsupported gnome-build-meta pin schema {pin.get('schema')}")
    if not pin.get("mapping"):
        raise ValueError("gnome-build-meta pin has an empty mapping")
    return pin


def _verify_checkout(loader: Loader, commit: str) -> None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(loader.root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        # Not a git checkout; treat as an exported snapshot and rely on the
        # pin file for provenance.
        return None
    head = proc.stdout.strip()
    if head != commit and not head.startswith(commit[:12]):
        raise SystemExit(
            f"gnome-build-meta checkout is at {head}, not the pinned commit "
            f"{commit}. Pass --no-verify to audit an exported snapshot instead."
        )
    return head


def render_markdown(report: dict) -> str:
    pin = report["generated_for"]
    lines = [
        f"# GNOME recipes vs gnome-build-meta audit",
        "",
        f"- GNOME release: `{pin['release_tag']}` @ `{pin['release_commit']}`",
        f"- factory revision audited: `{pin['factory_base']}`",
        "",
        "Every difference is classified, not treated as an automatic defect. "
        "`needs_review` entries carry evidence for a human to re-classify as "
        "intentional Fedora/RPM integration, intentional Hummingbird/downstream "
        "policy, or actionable drift.",
        "",
    ]
    totals: dict[str, int] = {}
    for entry in report["packages"]:
        totals[entry["classification"]] = totals.get(entry["classification"], 0) + 1
    lines.append("## Summary")
    lines.append("")
    for classification in sorted(totals):
        lines.append(f"- **{classification}**: {totals[classification]}")
    lines.append("")

    for entry in report["packages"]:
        lines.append(f"## {entry['rpm_name']} → `{entry['gbm_element']}`")
        lines.append("")
        lines.append(f"- Classification: **{entry['classification']}**")
        if entry["reason"]:
            lines.append(f"- Reason: {entry['reason']}")
        lines.append("")
        if entry["factory"].get("version"):
            lines.append(f"- Factory version: `{entry['factory']['version']}`")
        gbm_src = entry["gnome_build_meta"].get("primary_source")
        if gbm_src and gbm_src.get("url"):
            lines.append(f"- GBM primary source: `{gbm_src['url']}`")
        if entry["factory"].get("patches"):
            lines.append(f"- Factory patches: {', '.join(entry['factory']['patches'])}")
        if entry["gnome_build_meta"].get("patches"):
            lines.append("- GBM patches: " + ", ".join(entry["gnome_build_meta"]["patches"]))
        ffeat = entry["factory"].get("features") or {}
        gfeat = entry["gnome_build_meta"].get("features") or {}
        if ffeat or gfeat:
            lines.append("- Feature options: see JSON report for the full diff.")
        dep_count = (
            len(entry["gnome_build_meta"].get("depends", []))
            + len(entry["gnome_build_meta"].get("build_depends", []))
            + len(entry["gnome_build_meta"].get("runtime_depends", []))
        )
        lines.append(f"- GBM dependency edges: {dep_count}")
        lines.append("")
    lines.append("")
    lines.append("_This is a non-gating evidence report. It is safe to regenerate "
                 "for a newer GNOME release without rewriting the tool._")
    return "\n".join(lines)


def parse_args(argv):
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Audit GNOME RPM recipes against gnome-build-meta."
    )
    parser.add_argument("--gbm-dir", type=Path, required=True,
                        help="path to a gnome-build-meta checkout at the pinned commit")
    parser.add_argument("--pin", type=Path, default=repo / "config" / "gnome-build-meta.json")
    parser.add_argument("--sources", type=Path, default=repo / "config" / "upstream-sources.json")
    parser.add_argument("--packages-dir", type=Path, default=repo / "packages")
    parser.add_argument("--json-out", type=Path, default=repo / "reports" / "audit-gnome-build-meta.json")
    parser.add_argument("--markdown-out", type=Path, default=repo / "reports" / "audit-gnome-build-meta.md")
    parser.add_argument("--no-verify", action="store_true",
                        help="do not require --gbm-dir to be a git checkout at the pinned commit")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    pin = load_pin(args.pin)
    if not args.gbm_dir.exists():
        print(f"error: gnome-build-meta checkout not found: {args.gbm_dir}", file=sys.stderr)
        return 2

    loader = Loader(args.gbm_dir)
    if not args.no_verify:
        _verify_checkout(loader, pin["source"]["release_commit"])
    aliases = _aliases(loader)

    factory_sources = _load_factory_sources(args.sources)
    if not args.packages_dir.exists():
        print(f"warning: packages dir not found: {args.packages_dir}", file=sys.stderr)

    report = build_report(pin, loader, aliases, factory_sources, args.packages_dir)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    args.markdown_out.write_text(render_markdown(report) + "\n")

    print(f"audit written: {args.json_out}")
    print(f"audit written: {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
