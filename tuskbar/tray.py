"""System tray icon with status indicator and quick actions."""

import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .dashboard import DashboardWindow
from .pg import PgCluster

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

STATUS_ICON_FILES = {
    "running": os.path.join(ASSETS_DIR, "tuskbar-running.svg"),
    "stopped": os.path.join(ASSETS_DIR, "tuskbar-stopped.svg"),
    "error": os.path.join(ASSETS_DIR, "tuskbar-stopped.svg"),
    "unknown": os.path.join(ASSETS_DIR, "tuskbar.svg"),
}


class TuskbarTray(QSystemTrayIcon):
    def __init__(self, cluster: PgCluster):
        super().__init__()
        self.cluster = cluster
        self.dashboard: DashboardWindow | None = None

        # Initial icon
        self._update_icon("unknown")

        # Menu
        self.menu = QMenu()

        self.status_action = QAction("Status: checking...")
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        self.start_action = QAction("Start")
        self.start_action.triggered.connect(self._start)
        self.menu.addAction(self.start_action)

        self.stop_action = QAction("Stop")
        self.stop_action.triggered.connect(self._stop)
        self.menu.addAction(self.stop_action)

        self.restart_action = QAction("Restart")
        self.restart_action.triggered.connect(self._restart)
        self.menu.addAction(self.restart_action)

        self.menu.addSeparator()

        self.psql_action = QAction("Open psql")
        self.psql_action.triggered.connect(self._open_psql)
        self.menu.addAction(self.psql_action)

        dashboard_action = QAction("Dashboard")
        dashboard_action.triggered.connect(self._show_dashboard)
        self.menu.addAction(dashboard_action)

        self.menu.addSeparator()

        quit_action = QAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        self.menu.addAction(quit_action)

        self.setContextMenu(self.menu)

        # On KDE, left-click opens dashboard; right-click shows context menu (handled by Qt)
        self.activated.connect(self._on_activated)

        # Workaround: on some KDE/Wayland setups, middle-click also triggers
        # We only handle DoubleClick and Trigger (single left-click)

        # Poll status
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll_status)
        self.timer.start(5000)
        self._poll_status()

    def _update_icon(self, status: str):
        icon_path = STATUS_ICON_FILES.get(status, STATUS_ICON_FILES["unknown"])
        self.setIcon(QIcon(icon_path))
        self.setToolTip(f"Tuskbar — PostgreSQL {status} (port {self.cluster.port})")

    def _poll_status(self):
        status = self.cluster.status()
        running = status == "running"

        self._update_icon(status)
        self.status_action.setText(f"PostgreSQL: {status.upper()}")

        self.start_action.setEnabled(not running)
        self.stop_action.setEnabled(running)
        self.restart_action.setEnabled(running)
        self.psql_action.setEnabled(running)

    def _start(self):
        ok, msg = self.cluster.start()
        if not ok:
            self.showMessage("Tuskbar", f"Start failed: {msg}", QSystemTrayIcon.MessageIcon.Warning)
        self._poll_status()

    def _stop(self):
        ok, msg = self.cluster.stop()
        if not ok:
            self.showMessage("Tuskbar", f"Stop failed: {msg}", QSystemTrayIcon.MessageIcon.Warning)
        self._poll_status()

    def _restart(self):
        ok, msg = self.cluster.restart()
        if not ok:
            self.showMessage("Tuskbar", f"Restart failed: {msg}", QSystemTrayIcon.MessageIcon.Warning)
        self._poll_status()

    def _open_psql(self):
        import shutil
        import subprocess
        psql_cmd = f"psql -p {self.cluster.port} postgres; exec bash"
        if shutil.which("konsole"):
            subprocess.Popen(["konsole", "-e", "bash", "-c", psql_cmd])
        else:
            subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-c", psql_cmd])

    def _show_dashboard(self):
        if self.dashboard is None:
            self.dashboard = DashboardWindow(self.cluster)
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()
        self.dashboard.refresh()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_dashboard()
