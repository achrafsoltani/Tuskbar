"""Dashboard window — shows cluster status, databases, and actions."""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .help import HelpDialog
from .pg import PgCluster


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore
    return f"{nbytes:.1f} PB"


ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


class DashboardWindow(QMainWindow):
    def __init__(self, cluster: PgCluster):
        super().__init__()
        self.cluster = cluster
        self.setWindowTitle("Tuskbar — PostgreSQL Manager")
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "tuskbar-window.svg")))
        self.setMinimumSize(560, 420)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- Header ---
        header = QLabel("Tuskbar")
        header.setFont(QFont("", 18, QFont.Weight.Bold))
        layout.addWidget(header)

        # --- Status row ---
        self.status_label = QLabel()
        self.status_label.setFont(QFont("", 12))
        layout.addWidget(self.status_label)

        # --- Info row ---
        self.version_label = QLabel()
        self.port_label = QLabel()
        self.datadir_label = QLabel()
        for lbl in (self.version_label, self.port_label, self.datadir_label):
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(lbl)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.restart_btn = QPushButton("Restart")
        self.psql_btn = QPushButton("Open psql")

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.restart_btn.clicked.connect(self._restart)
        self.psql_btn.clicked.connect(self._open_psql)

        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self._show_help)
        self.quit_btn = QPushButton("Quit Tuskbar")
        self.quit_btn.clicked.connect(QApplication.instance().quit)

        for btn in (self.start_btn, self.stop_btn, self.restart_btn, self.psql_btn):
            btn.setMinimumHeight(32)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        # --- Autostart toggle ---
        self.autostart_check = QCheckBox("Start PostgreSQL on boot")
        self.autostart_check.toggled.connect(self._toggle_autostart)
        layout.addWidget(self.autostart_check)

        # --- Database table ---
        db_header = QLabel("Databases")
        db_header.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(db_header)

        self.db_table = QTableWidget()
        self.db_table.setColumnCount(3)
        self.db_table.setHorizontalHeaderLabels(["Name", "Size", ""])
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.db_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.db_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.db_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.db_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.db_table.verticalHeader().setVisible(False)
        layout.addWidget(self.db_table)

        # --- Bottom buttons ---
        layout.addStretch()
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.help_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(self.quit_btn)
        layout.addLayout(bottom_row)

        # --- Refresh timer ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)

        self.refresh()

    def refresh(self):
        status = self.cluster.status()
        running = status == "running"

        colour = {"running": "#27ae60", "stopped": "#dc3545"}.get(status, "#ffc107")
        self.status_label.setText(
            f'Status: <span style="color:{colour}; font-weight:bold">{status.upper()}</span>'
        )

        self.version_label.setText(self.cluster.version())
        self.port_label.setText(f"Port: {self.cluster.port}")
        self.datadir_label.setText(f"Data: {self.cluster.data_dir}")

        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.restart_btn.setEnabled(running)
        self.psql_btn.setEnabled(running)

        # Autostart checkbox
        autostart = self.cluster.autostart_enabled()
        if autostart is None:
            self.autostart_check.setVisible(False)
        else:
            self.autostart_check.setVisible(True)
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(autostart)
            self.autostart_check.blockSignals(False)

        self._refresh_databases(running)

    def _refresh_databases(self, running: bool):
        self.db_table.setRowCount(0)
        if not running:
            return

        databases = self.cluster.databases()
        self.db_table.setRowCount(len(databases))

        for i, db in enumerate(databases):
            name_item = QTableWidgetItem(db["name"])
            size_item = QTableWidgetItem(_human_size(db["size"]))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            copy_btn = QPushButton("Copy URI")
            copy_btn.setFixedHeight(26)
            dbname = db["name"]
            copy_btn.clicked.connect(lambda checked=False, d=dbname: self._copy_uri(d))

            self.db_table.setItem(i, 0, name_item)
            self.db_table.setItem(i, 1, size_item)
            self.db_table.setCellWidget(i, 2, copy_btn)

    def _copy_uri(self, dbname: str):
        uri = self.cluster.connection_string(dbname)
        app = QApplication.instance()
        if app:
            app.clipboard().setText(uri)

    def _start(self):
        ok, msg = self.cluster.start()
        if not ok:
            QMessageBox.warning(self, "Start failed", msg)
        self.refresh()

    def _stop(self):
        ok, msg = self.cluster.stop()
        if not ok:
            QMessageBox.warning(self, "Stop failed", msg)
        self.refresh()

    def _restart(self):
        ok, msg = self.cluster.restart()
        if not ok:
            QMessageBox.warning(self, "Restart failed", msg)
        self.refresh()

    def _toggle_autostart(self, checked: bool):
        ok, msg = self.cluster.set_autostart(checked)
        if not ok:
            QMessageBox.warning(self, "Autostart failed", msg)
        self.refresh()

    def _show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def _open_psql(self):
        import shutil
        import subprocess
        selected = self.db_table.selectedItems()
        dbname = selected[0].text() if selected else "postgres"
        psql_cmd = f"psql -p {self.cluster.port} {dbname}; exec bash"
        if shutil.which("konsole"):
            subprocess.Popen(["konsole", "-e", "bash", "-c", psql_cmd])
        else:
            subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-c", psql_cmd])
