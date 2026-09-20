# GNOME recipes vs gnome-build-meta audit

- GNOME release: `51.0` @ `a50b8c9de35f51c6a646c8178cde3c2c176725b6`
- factory revision audited: `af53b1edba9f653fd3255cfdeca85111c85e5ed8`

Every difference is classified, not treated as an automatic defect. `needs_review` entries carry evidence for a human to re-classify as intentional Fedora/RPM integration, intentional Hummingbird/downstream policy, or actionable drift.

## Summary

- **unmapped**: 26

## mutter → `core/mutter.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- GBM dependency edges: 0

## gnome-shell → `core/gnome-shell.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- Factory patches: gnome-shell-favourite-apps-firefox.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gnome-control-center → `core/gnome-control-center.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gnome-session → `core/gnome-session.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- Factory patches: 0001-Fedora-Set-grub-boot-flags-on-shutdown-reboot.patch
- GBM dependency edges: 0

## gnome-settings-daemon → `core/gnome-settings-daemon.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- GBM dependency edges: 0

## gnome-desktop3 → `core/gnome-desktop.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.alpha`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gnome-bluetooth → `core/gnome-bluetooth.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `47.2`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## nautilus → `core/nautilus.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51~beta`
- Factory patches: default-terminal.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gjs → `sdk/gjs.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.89.2`
- GBM dependency edges: 0

## gtk3 → `sdk/gtk+-3.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `3.24.52`
- Factory patches: 9852_export_xdg_toplevel.patch, 9956_pointer_focus.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gtk4 → `sdk/gtk.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `4.23.3`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## libadwaita → `sdk/libadwaita.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.10.beta.1`
- Factory patches: fix-sassc-requirement-for-tarball-builds.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gdk-pixbuf2 → `sdk/gdk-pixbuf.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `2.44.8`
- Factory patches: CVE-2026-16768.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## pango → `sdk/pango.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.58.2`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## cairo → `sdk/cairo.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.18.4`
- Factory patches: cairo-multilib.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## librsvg2 → `sdk/librsvg.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `2.62.3`
- Factory patches: 0001-Fedora-Drop-dependencies-required-for-benchmarking.patch, 0002-Fedora-Drop-dependencies-and-references-to-mutation-.patch, 0003-Fedora-Drop-windows-specific-dependencies.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gsettings-desktop-schemas → `sdk/gsettings-desktop-schemas.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.beta`
- GBM dependency edges: 0

## glib-networking → `sdk/glib-networking.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `2.90~alpha`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gvfs → `sdk-deps/gvfs.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.61.91`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gvfs-client → `sdk/gvfs-client.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.61.91`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gvfs-daemon → `core/gvfs-daemon.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `1.61.91`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## gnome-online-accounts → `core-deps/gnome-online-accounts.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `3.58.1`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## evolution-data-server → `core-deps/evolution-data-server.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `3.61.3`
- Factory patches: Make-DBUS_SERVICES_PREFIX-runtime-configurable.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## localsearch → `core-deps/localsearch.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `3.12~beta`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## tinysparql → `core-deps/localsearch.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `3.12~beta`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0

## xdg-desktop-portal-gnome → `core-deps/xdg-desktop-portal-gnome.bst`

- Classification: **unmapped**
- Reason: no gnome-build-meta element in the pinned tree

- Factory version: `51.alpha`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 0


_This is a non-gating evidence report. It is safe to regenerate for a newer GNOME release without rewriting the tool._
