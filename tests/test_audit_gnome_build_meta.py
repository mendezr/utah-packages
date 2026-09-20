#!/usr/bin/env python3

"""Unit tests for tools/audit_gnome_build_meta.py.

The audit tool must be deterministic and reason about BuildStream includes and
dependency composition deliberately (the issue explicitly rules out a
regex-only scan). These tests exercise the pieces that make it deterministic:
name mapping, secondary sources, dependency categories, includes, feature-option
extraction, release-line comparison and classification.
"""

from pathlib import Path
import json
import tempfile
import unittest

from tools.audit_gnome_build_meta import (
    ALIGNED,
    NEEDS_REVIEW,
    UNMAPPED,
    Loader,
    _aliases,
    classify,
    element_patch_sources,
    meson_options,
    release_line,
    resolve_element,
    same_release_line,
    spec_patches,
    _rpm_base_name,
    build_report,
)

ALIASES = """\
aliases:
  gnome_downloads: https://download.gnome.org/sources/
  gnome: https://gitlab.gnome.org/GNOME/
"""

GCC_FOR_RECC = """\
filename:
- freedesktop-sdk.bst:components/gcc.bst
config:
  digest-environment: RECC_REMOTE_PLATFORM_chrootRootDigest
"""

MUTTER_BST = """\
kind: meson

sources:
- kind: tar
  url: gnome_downloads:mutter/51/mutter-51.0.tar.xz
  ref: 5d28f3ae225692428fcafb96500d673f34328b698b86960c9c1460d0b1d983b3
- kind: git_repo
  url: gnome:gvdb.git
  directory: subprojects/gvdb
  ref: b54bc5da25127ef416858a3ad92e57159ff565b3

build-depends:
- (@): include/gcc-for-recc.yml
- buildsystems/meson.bst
- core-deps/python-argcomplete.bst

runtime-depends:
- core/gnome-control-center.bst

depends:
- sdk/glib.bst
- sdk/gobject-introspection.bst
- core/gnome-desktop.bst

variables:
  meson-local: >-
    -Dxwayland_initfd=enabled
    -Dprofiler=true
"""

GVFS_DAEMON_BST = """\
kind: filter

build-depends:
- sdk-deps/gvfs.bst

runtime-depends:
- sdk/glib.bst
"""

PIN = {
    "schema": 1,
    "source": {
        "name": "gnome-build-meta",
        "url": "https://gitlab.gnome.org/GNOME/gnome-build-meta.git",
        "release_tag": "51.0",
        "release_commit": "a50b8c9de35f51c6a646c8178cde3c2c176725b6",
    },
    "element_path": {"project_conf": "project.conf", "root": "elements"},
    "factory_alias": {},
    "mapping": {
        "mutter": "core/mutter.bst",
        "gvfs-daemon": "core/gvfs-daemon.bst",
    },
    "unmapped": [],
}


def write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def make_gbm_tree(root: Path) -> Path:
    write(root, "include/aliases.yml", ALIASES)
    write(root, "include/gcc-for-recc.yml", GCC_FOR_RECC)
    write(root, "elements/core/mutter.bst", MUTTER_BST)
    write(root, "elements/core/gvfs-daemon.bst", GVFS_DAEMON_BST)
    return root


class ReleaseLineTests(unittest.TestCase):
    def test_gnome_cycle_uses_single_major(self) -> None:
        self.assertEqual(release_line("51.0"), "51")
        self.assertEqual(release_line("51.beta"), "51")

    def test_library_uses_major_minor(self) -> None:
        self.assertEqual(release_line("1.10.beta.1"), "1.10")
        self.assertEqual(release_line("4.23.3"), "4.23")
        self.assertEqual(release_line("2.62.3"), "2.62")

    def test_same_release_line(self) -> None:
        self.assertTrue(same_release_line("51.beta", "51.0"))
        self.assertTrue(same_release_line("1.10.beta.1", "1.10.0"))
        self.assertTrue(same_release_line("3.12.beta", "3.12.0"))
        self.assertFalse(same_release_line("4.23.3", "4.24.0"))
        self.assertFalse(same_release_line("1.89.2", "1.90.0"))
        self.assertFalse(same_release_line("", "1.0"))

    def test_rpm_base_name_strips_trailing_digits(self) -> None:
        self.assertEqual(_rpm_base_name("gnome-desktop3"), "gnome-desktop")
        self.assertEqual(_rpm_base_name("gtk4"), "gtk")
        self.assertEqual(_rpm_base_name("gdk-pixbuf2"), "gdk-pixbuf")
        self.assertEqual(_rpm_base_name("librsvg2"), "librsvg")
        self.assertEqual(_rpm_base_name("nautilus"), "nautilus")


class ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_name_mapping_from_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pin_path = write(Path(tmp), "pin.json", json.dumps(PIN))
            from tools.audit_gnome_build_meta import load_pin
            pin = load_pin(pin_path)
            self.assertEqual(pin["mapping"]["mutter"], "core/mutter.bst")

    def test_resolve_includes_and_kind(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(el.kind, "meson")
        # include/gcc-for-recc.yml is resolved and recorded, not treated as a dep.
        self.assertIn("include/gcc-for-recc.yml", el.includes)
        self.assertNotIn("freedesktop-sdk.bst:components/gcc.bst", el.build_depends)
        self.assertIn("buildsystems/meson.bst", el.build_depends)

    def test_primary_source_expands_alias(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(
            el.primary_source["url"],
            "https://download.gnome.org/sources/mutter/51/mutter-51.0.tar.xz",
        )

    def test_secondary_sources_captures_wrap(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        secondaries = el.sources[1:]
        self.assertEqual(len(secondaries), 1)
        self.assertEqual(secondaries[0]["directory"], "subprojects/gvdb")
        self.assertEqual(secondaries[0]["kind"], "git_repo")

    def test_dependency_categories_split(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(el.runtime_depends, ["core/gnome-control-center.bst"])
        self.assertIn("sdk/glib.bst", el.depends)
        self.assertIn("core/gnome-desktop.bst", el.depends)

    def test_feature_options_from_variables(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertIn("meson-local", el.variables)
        self.assertIn("profiler=true", el.variables["meson-local"])

    def test_filter_element_has_no_sources(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/gvfs-daemon.bst")
        self.assertEqual(el.kind, "filter")
        self.assertEqual(el.sources, [])

    def test_spec_features_and_patches(self) -> None:
        spec = (
            "Name: mutter\nVersion: 51.beta\n"
            "Patch: linux-fix.patch\n"
            "%meson \\\n"
            "  -Dprofiler=true \\\n"
            "  -Dxwayland_initfd=enabled \\\n"
            "  %{nil}\n"
        )
        opts = meson_options(spec)
        self.assertEqual(opts.get("profiler"), "true")
        self.assertEqual(opts.get("xwayland_initfd"), "enabled")
        self.assertEqual(spec_patches(spec), ["linux-fix.patch"])


class ClassifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_aligned_same_line(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, reason = classify(
            el, {"name": "mutter", "patches": []}, "51.beta", []
        )
        self.assertEqual(cls, ALIGNED)
        self.assertIn("51", reason)

    def test_patch_drift_is_needs_review(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, reason = classify(
            el, {"name": "mutter", "patches": ["local.patch"]}, "51.beta", []
        )
        self.assertEqual(cls, NEEDS_REVIEW)
        self.assertIn("patch", reason)

    def test_line_mismatch_is_needs_review(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, _ = classify(el, {"name": "mutter", "patches": []}, "45.0", [])
        self.assertEqual(cls, NEEDS_REVIEW)

    def test_missing_element_is_unmapped(self) -> None:
        cls, _ = classify(None, {"name": "mutter", "patches": []}, "51.0", [])
        self.assertEqual(cls, UNMAPPED)

    def test_filter_element_aligned_membership(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/gvfs-daemon.bst")
        cls, _ = classify(el, {"name": "gvfs", "patches": []}, "1.61.91", [])
        self.assertEqual(cls, ALIGNED)


class ReportTests(unittest.TestCase):
    def test_build_report_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_gbm_tree(root)
            pin_path = write(root, "pin.json", json.dumps(PIN))
            sources = {
                "mutter": {"name": "mutter", "version": "51.beta", "filename": "mutter-51.beta.tar.xz"},
                "gvfs": {"name": "gvfs", "version": "1.61.91", "filename": "gvfs-1.61.91.tar.xz"},
            }
            packages_dir = write(root, "packages/mutter/mutter.spec",
                                 "Name: mutter\nVersion: 51.beta\n%meson\n")

            loader = Loader(root)
            report = build_report(
                json.loads(pin_path.read_text()), loader,
                _aliases(loader), sources, packages_dir.parent,
            )
            self.assertEqual(len(report["packages"]), 2)
            classes = {p["rpm_name"]: p["classification"] for p in report["packages"]}
            self.assertEqual(classes["mutter"], ALIGNED)


if __name__ == "__main__":
    unittest.main()
