#!/bin/bash
set -euo pipefail

APP_NAME="tuskbar"
VERSION="0.1.0"
RELEASE="1"
DIST_DIR="dist"

echo "=== Building ${APP_NAME} ${VERSION} .rpm package ==="

# Check for rpmbuild
if ! command -v rpmbuild > /dev/null 2>&1; then
    echo "Error: rpmbuild not found. Install with: sudo dnf install rpm-build"
    exit 1
fi

# Clean
rm -rf build/rpm/ "${DIST_DIR}/${APP_NAME}-${VERSION}-${RELEASE}.noarch.rpm"
mkdir -p "${DIST_DIR}"

# RPM build tree
RPM_DIR="build/rpm"
mkdir -p "${RPM_DIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Create tarball
TAR_DIR="${APP_NAME}-${VERSION}"
mkdir -p "build/${TAR_DIR}"
cp -r tuskbar/ "build/${TAR_DIR}/"
cp -r assets/ "build/${TAR_DIR}/"
cp requirements.txt "build/${TAR_DIR}/"
tar czf "${RPM_DIR}/SOURCES/${TAR_DIR}.tar.gz" -C build "${TAR_DIR}"
rm -rf "build/${TAR_DIR}"

# Generate spec file
cat > "${RPM_DIR}/SPECS/${APP_NAME}.spec" << SPEC
Name:           ${APP_NAME}
Version:        ${VERSION}
Release:        ${RELEASE}%{?dist}
Summary:        PostgreSQL system tray manager for Linux
License:        MIT
URL:            https://github.com/AchrafSoltani/Tuskbar
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
Requires:       python3
Requires:       python3-pyside6
Requires:       python3-psycopg2
Requires:       python3-pyyaml
Requires:       postgresql
Recommends:     postgresql-server

%description
Tuskbar is a lightweight system tray application for managing
PostgreSQL servers on Linux. Features include start/stop/restart
via systemctl, database listing, connection string copy, and
quick psql terminal access.

%prep
%setup -q

%install
rm -rf %{buildroot}

# Python package
mkdir -p %{buildroot}/usr/share/%{name}/tuskbar
cp -r tuskbar/* %{buildroot}/usr/share/%{name}/tuskbar/

# Assets
mkdir -p %{buildroot}/usr/share/%{name}/assets
cp assets/*.svg %{buildroot}/usr/share/%{name}/assets/

# Requirements
cp requirements.txt %{buildroot}/usr/share/%{name}/

# Launcher
mkdir -p %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/%{name} << 'EOF'
#!/bin/bash
exec python3 -m tuskbar "\$@"
EOF
chmod 755 %{buildroot}/usr/bin/%{name}

# Desktop entry
mkdir -p %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/share/applications/%{name}.desktop << EOF
[Desktop Entry]
Name=Tuskbar
Comment=PostgreSQL system tray manager
Exec=%{name}
Icon=%{name}
Terminal=false
Type=Application
Categories=Development;Database;
Keywords=postgresql;postgres;database;tray;
StartupNotify=false
EOF

# Icon
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps
cp assets/tuskbar-window.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/%{name}.svg

%post
update-desktop-database -q /usr/share/applications/ 2>/dev/null || true
gtk-update-icon-cache -q /usr/share/icons/hicolor/ 2>/dev/null || true

%files
/usr/bin/%{name}
/usr/share/%{name}/
/usr/share/applications/%{name}.desktop
/usr/share/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* $(date '+%a %b %d %Y') Achraf Soltani <achraf.soltani@pm.me> - ${VERSION}-${RELEASE}
- Initial release
- System tray with status icon
- Dashboard with database listing
- Start/stop/restart via systemctl
- Copy connection URI
- Open psql in terminal
SPEC

# Build RPM
rpmbuild --define "_topdir $(pwd)/${RPM_DIR}" -bb "${RPM_DIR}/SPECS/${APP_NAME}.spec"

# Copy result
find "${RPM_DIR}/RPMS" -name "*.rpm" -exec cp {} "${DIST_DIR}/" \;

echo "=== Built: ${DIST_DIR}/${APP_NAME}-${VERSION}-${RELEASE}.noarch.rpm ==="
