# Hummingbird has no system Rust crate stack; bundle gtk-rs, clap and
# libglycin-rebind with this application rather than building crate RPMs.
%bcond bundled_rust_deps 1

Name:           gst-thumbnailers
Version:        1.1.0
Release:        %autorelease
Summary:        GStreamer Thumbnailers

%gnome_check_version

SourceLicense:  GPL-3.0-or-later
# Rust dependencies:
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception
# BSD-3-Clause OR Apache-2.0
# GPL-3.0-or-later
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
# Zlib OR Apache-2.0 OR MIT
License:        %{shrink:
    GPL-3.0-or-later
    AND Apache-2.0 WITH LLVM-exception
    AND MIT
    AND (Apache-2.0 OR MIT)
    AND (BSD-3-Clause OR Apache-2.0)
    AND (Unlicense OR MIT)
    AND (Zlib OR Apache-2.0 OR MIT)
}
# LICENSE.dependencies contains a full license breakdown

URL:            https://gitlab.gnome.org/GNOME/gst-thumbnailers
Source:         https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{gnome_tarball_version}.tar.xz

Source1:        gst-thumbnailers-%{version}-vendor.tar.xz
Source2:        Cargo.lock

Patch:          0001-meson-adapt-for-RPM-package-build-environment.patch
Patch:          0002-cargo-drop-benchmarks-and-benchmark-only-dependencie.patch
Patch:          0003-Bump-libglycin-rebind-to-0.2.0-beta-for-GNOME-51.bet.patch

BuildRequires:  cargo-rpm-macros
BuildRequires:  meson >= 1.2

BuildRequires:  pkgconfig(glycin-2) >= 2.0.0
BuildRequires:  pkgconfig(gstreamer-1.0) >= 1.26.0

# GStreamer plugin dependencies (tests)
BuildRequires:  gstreamer1-plugins-base
BuildRequires:  gstreamer1-plugins-good

# GStreamer plugin dependencies (runtime)
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good

%description
%{summary}.

%prep
%if %{with bundled_rust_deps}
%autosetup -n gst-thumbnailers-%{gnome_tarball_version} -p1 -a1
cp %{SOURCE2} Cargo.lock
%cargo_prep -v vendor
%else
%autosetup -n gst-thumbnailers-%{gnome_tarball_version} -p1
%cargo_prep
%endif

%if %{without bundled_rust_deps}
%generate_buildrequires
%cargo_generate_buildrequires
%endif

%build
%meson
%meson_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%if %{with bundled_rust_deps}
%cargo_vendor_manifest
%endif

%install
%meson_install

%check
%ifnarch s390x
# https://gitlab.gnome.org/GNOME/gst-thumbnailers/-/issues/17
%meson_test
%endif

%files
%license LICENSE
%license LICENSE.dependencies
%if %{with bundled_rust_deps}
%license cargo-vendor.txt
%endif
%doc README.md
%doc NEWS
%{_bindir}/gst-audio-thumbnailer
%{_bindir}/gst-video-thumbnailer
%dir %{_datadir}/thumbnailers
%{_datadir}/thumbnailers/gst-audio-thumbnailer.thumbnailer
%{_datadir}/thumbnailers/gst-video-thumbnailer.thumbnailer

%changelog
%autochangelog
