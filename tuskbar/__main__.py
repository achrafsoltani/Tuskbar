"""Tuskbar — PostgreSQL system tray manager."""

import fcntl
import os
import sys
import tempfile

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .pg import PgCluster, detect_data_dir
from .tray import TuskbarTray

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

LOCK_FILE = os.path.join(tempfile.gettempdir(), "tuskbar.lock")


def _acquire_lock():
    """Ensure only one instance of Tuskbar runs at a time.
    Uses flock — the lock is automatically released when the process exits.
    Never delete the lock file manually."""
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Another instance holds the lock — try to kill it and retry
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 9)
            import time
            time.sleep(1)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ValueError, ProcessLookupError, OSError):
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
    app.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "tuskbar-window.svg")))
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    tray = TuskbarTray(cluster)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
