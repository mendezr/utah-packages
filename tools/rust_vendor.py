#!/usr/bin/env python3
"""Reproduce a recipe's Source1 with cargo vendor --versioned-dirs.

Run in the factory's pinned Packit container. Cargo.lock is a reviewed recipe
input, not something resolved afresh during normal builds. --update-lock is
only for preparing a dependency update; review its output before committing it.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request


def generate(name: str, output: Path, *, update_lock: bool = False) -> Path:
    root = Path(__file__).resolve().parents[1]
    package = root / "packages" / name
    config = json.loads((package / "rust-vendor.json").read_text())
    lock = next(entry for entry in json.loads((root / "config/upstream-sources.json").read_text())["packages"]
                if entry["name"] == name)
    request = urllib.request.Request(lock["url"], headers={"User-Agent": "utah-packages-rust-vendor/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    if hashlib.sha512(payload).hexdigest() != lock["sha512"]:
        raise ValueError("upstream source SHA-512 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rust-vendor-") as scratch:
        scratch = Path(scratch)
        archive = scratch / lock["filename"]
        archive.write_bytes(payload)
        with tarfile.open(archive) as source:
            source.extractall(scratch, filter="data")
        tree = scratch / config["directory"]
        for patch in config["patches"]:
            subprocess.run(["patch", "-p1", "--batch", "-i", str(package / patch)], cwd=tree, check=True)
        if update_lock:
            subprocess.run(["cargo", "generate-lockfile"], cwd=tree, check=True)
            shutil.copy2(tree / "Cargo.lock", output / "Cargo.lock")
        else:
            shutil.copy2(package / "Cargo.lock", tree / "Cargo.lock")
        subprocess.run(["cargo", "vendor", "--locked", "--versioned-dirs", "vendor"], cwd=tree, check=True)
        target = output.resolve() / config["filename"]
        subprocess.run([
            "tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0", "--numeric-owner",
            "-cJf", str(target), "vendor",
        ], cwd=tree, check=True, env={**__import__("os").environ, "XZ_OPT": "-9e -T1"})
        (output / (target.name + ".sha512")).write_text(hashlib.sha512(target.read_bytes()).hexdigest() + "\n")
        return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("output", type=Path)
    parser.add_argument("--update-lock", action="store_true")
    args = parser.parse_args()
    print(generate(args.package, args.output, update_lock=args.update_lock))
