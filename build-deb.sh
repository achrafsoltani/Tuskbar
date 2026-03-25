#!/bin/bash
set -euo pipefail

APP_NAME="tuskbar"
VERSION="0.1.0"
ARCH="amd64"
PKG_DIR="build/${APP_NAME}_${VERSION}_${ARCH}"
DIST_DIR="dist"

echo "=== Building ${APP_NAME} ${VERSION} .deb package ==="

# Clean
rm -rf build/ "${DIST_DIR}/${APP_NAME}_${VERSION}_${ARCH}.deb"
mkdir -p "${DIST_DIR}"

# Directory structure
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/share/${APP_NAME}"
mkdir -p "${PKG_DIR}/usr/share/${APP_NAME}/assets"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"

# Copy Python package
cp -r tuskbar/ "${PKG_DIR}/usr/share/${APP_NAME}/tuskbar/"

# Copy assets
cp assets/*.svg "${PKG_DIR}/usr/share/${APP_NAME}/assets/"

# Copy requirements
cp requirements.txt "${PKG_DIR}/usr/share/${APP_NAME}/"

# Create launcher script
cat > "${PKG_DIR}/usr/bin/${APP_NAME}" << 'LAUNCHER'
#!/bin/bash
exec python3 -m tuskbar "$@"
LAUNCHER
chmod 755 "${PKG_DIR}/usr/bin/${APP_NAME}"

# Desktop entry
cat > "${PKG_DIR}/usr/share/applications/${APP_NAME}.desktop" << DESKTOP
[Desktop Entry]
Name=Tuskbar
Comment=PostgreSQL system tray manager
Exec=${APP_NAME}
Icon=${APP_NAME}
Terminal=false
Type=Application
Categories=Development;Database;
Keywords=postgresql;postgres;database;tray;
StartupNotify=false
DESKTOP

# App icon (scalable)
cp assets/tuskbar-window.svg "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"

# Control file
cat > "${PKG_DIR}/DEBIAN/control" << CONTROL
Package: ${APP_NAME}
Version: ${VERSION}
Section: database
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-pyside6, python3-psycopg2 | python3-psycopg, python3-yaml, postgresql-client
Recommends: postgresql
Maintainer: Achraf Soltani <achraf.soltani@pm.me>
Homepage: https://github.com/AchrafSoltani/Tuskbar
Description: PostgreSQL system tray manager for Linux
 Tuskbar is a lightweight system tray application for managing
 PostgreSQL servers on Linux. Features include start/stop/restart
 via systemctl, database listing, connection string copy, and
 quick psql terminal access.
CONTROL

# Post-install script
cat > "${PKG_DIR}/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e

# Update desktop database
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications/ 2>/dev/null || true
fi

# Update icon cache
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor/ 2>/dev/null || true
fi

# Install Python dependencies if needed
python3 -c "import psycopg" 2>/dev/null || pip3 install --break-system-packages psycopg 2>/dev/null || true
python3 -c "import PySide6" 2>/dev/null || pip3 install --break-system-packages PySide6 2>/dev/null || true
python3 -c "import yaml" 2>/dev/null || pip3 install --break-system-packages PyYAML 2>/dev/null || true

echo ""
echo "Tuskbar installed successfully!"
echo "Launch from your application menu or run: tuskbar"
POSTINST
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

# Build .deb
dpkg-deb --build "${PKG_DIR}" "${DIST_DIR}/${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "=== Built: ${DIST_DIR}/${APP_NAME}_${VERSION}_${ARCH}.deb ==="
