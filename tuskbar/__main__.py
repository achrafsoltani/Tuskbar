"""Tuskbar — PostgreSQL system tray manager."""

import sys

from PySide6.QtWidgets import QApplication

from .pg import PgCluster, detect_data_dir
from .tray import TuskbarTray


def main():
    data_dir = detect_data_dir()
    if not data_dir:
        print("Error: Could not detect PostgreSQL data directory.", file=sys.stderr)
        print("Set PGDATA environment variable or pass --data-dir.", file=sys.stderr)
        sys.exit(1)

    cluster = PgCluster(data_dir=data_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("Tuskbar")
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    tray = TuskbarTray(cluster)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
