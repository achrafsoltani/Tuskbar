"""Tuskbar — PostgreSQL system tray manager."""

import fcntl
import os
import sys
import tempfile

from PySide6.QtWidgets import QApplication

from .pg import PgCluster, detect_data_dir
from .tray import TuskbarTray

LOCK_FILE = os.path.join(tempfile.gettempdir(), "tuskbar.lock")


def _acquire_lock():
    """Ensure only one instance of Tuskbar runs at a time."""
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Tuskbar is already running.", file=sys.stderr)
        sys.exit(0)
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    return lock_fd  # keep reference alive to hold the lock


def main():
    lock = _acquire_lock()

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
