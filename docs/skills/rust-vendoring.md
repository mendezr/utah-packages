---
name: rust-vendoring
description: Bundle checksum-locked Rust dependencies for application recipes on Hummingbird.
metadata:
  type: procedure
---

# Rust application dependencies

Hummingbird does not provide the gtk-rs/clap crate RPM stack. For applications
such as gst-thumbnailers, vendor dependencies per recipe; do not import a
standalone rust-libglycin-rebind recipe or its transitive crate RPMs. That crate
belongs in the application's vendor tree, along with gio, glib and clap.
This is the maintainer-approved direction in
[issue #527](https://github.com/projectbluefin/utah-packages/issues/527).

Use `%bcond bundled_rust_deps 1`, Source1 for the SHA-512-locked vendor tarball,
`%cargo_prep -v vendor`, and guard `%cargo_generate_buildrequires` with the
unbundled condition. Retain native library BuildRequires and real tests; bundled
Rust bindings do not replace the native libraries. Install the dependency
license report and `%cargo_vendor_manifest` output with the application.

## Preparing and reproducing a bundle

`tools/rust_vendor.py` reads the recipe's `rust-vendor.json`, verifies Source0
against its upstream lock, applies the listed patches, copies the reviewed
recipe Cargo.lock and runs `cargo vendor --locked --versioned-dirs`. The
patched manifest matters: gst-thumbnailers changes libglycin-rebind's version
and removes benchmark-only dependencies before vendoring.

Run generation only through **Reproduce Rust vendor sources**, on the pinned
Packit container and GitHub-hosted runner. For dependency changes, dispatch
with `update_lock` enabled, then review and commit the resulting Cargo.lock
and archive SHA-512. Normal reproduction uses the committed lock. The workflow
compares two generated archives; normalized archive ownership, timestamps,
ordering and single-threaded xz keep the output deterministic.

The lock and tarball must change together. A successful vendor run proves
source preparation, not that native compilation or thumbnail tests passed.
