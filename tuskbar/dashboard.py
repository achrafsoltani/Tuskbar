"""Dashboard window — tabbed interface for server, roles, and connections."""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .connections import ConnectionProfile, load_connections, save_connections
from .help import HelpDialog
from .pg import PgCluster

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore
    return f"{nbytes:.1f} PB"


# =========================================================================
# Main Dashboard Window
# =========================================================================

class DashboardWindow(QMainWindow):
    def __init__(self, cluster: PgCluster):
        super().__init__()
        self.cluster = cluster
        self.setWindowTitle("Tuskbar — PostgreSQL Manager")
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "tuskbar-window.svg")))
        self.setMinimumSize(620, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Header + status ---
        header_row = QHBoxLayout()
        header = QLabel("Tuskbar")
        header.setFont(QFont("", 16, QFont.Weight.Bold))
        self.status_label = QLabel()
        self.status_label.setFont(QFont("", 11))
        header_row.addWidget(header)
        header_row.addStretch()
        header_row.addWidget(self.status_label)
        layout.addLayout(header_row)

        # --- Info row ---
        info_row = QHBoxLayout()
        self.version_label = QLabel()
        self.port_label = QLabel()
        for lbl in (self.version_label, self.port_label):
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_row.addWidget(lbl)
        info_row.addStretch()
        layout.addLayout(info_row)

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
        for btn in (self.start_btn, self.stop_btn, self.restart_btn, self.psql_btn):
            btn.setMinimumHeight(30)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        # --- Autostart ---
        self.autostart_check = QCheckBox("Start PostgreSQL on boot")
        self.autostart_check.toggled.connect(self._toggle_autostart)
        layout.addWidget(self.autostart_check)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_databases_tab(), "Databases")
        self.tabs.addTab(self._build_roles_tab(), "Roles")
        self.tabs.addTab(self._build_connections_tab(), "Connections")
        layout.addWidget(self.tabs)

        # --- Bottom buttons ---
        bottom_row = QHBoxLayout()
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self._show_help)
        quit_btn = QPushButton("Quit Tuskbar")
        quit_btn.clicked.connect(QApplication.instance().quit)
        bottom_row.addWidget(help_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(quit_btn)
        layout.addLayout(bottom_row)

        # --- Timer ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    # ---- Tab builders ----

    def _build_databases_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
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
        return w

    def _build_roles_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        # Roles table
        self.roles_table = QTableWidget()
        self.roles_table.setColumnCount(5)
        self.roles_table.setHorizontalHeaderLabels(["Name", "Superuser", "Create DB", "Login", ""])
        self.roles_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            self.roles_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.roles_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.roles_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.roles_table.verticalHeader().setVisible(False)
        layout.addWidget(self.roles_table)

        # Buttons
        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create Role")
        create_btn.clicked.connect(self._create_role)
        btn_row.addWidget(create_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _build_connections_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        # Connections table
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(5)
        self.conn_table.setHorizontalHeaderLabels(["Name", "Host", "User", "Database", ""])
        self.conn_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            self.conn_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.conn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.conn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.conn_table.verticalHeader().setVisible(False)
        layout.addWidget(self.conn_table)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Connection")
        add_btn.clicked.connect(self._add_connection)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ---- Refresh ----

    def refresh(self):
        status = self.cluster.status()
        running = status == "running"

        colour = {"running": "#27ae60", "stopped": "#dc3545"}.get(status, "#ffc107")
        self.status_label.setText(
            f'<span style="color:{colour}; font-weight:bold">{status.upper()}</span>'
        )
        self.version_label.setText(self.cluster.version())
        self.port_label.setText(f"Port: {self.cluster.port}")

        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.restart_btn.setEnabled(running)
        self.psql_btn.setEnabled(running)

        autostart = self.cluster.autostart_enabled()
        if autostart is None:
            self.autostart_check.setVisible(False)
        else:
            self.autostart_check.setVisible(True)
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(autostart)
            self.autostart_check.blockSignals(False)

        self._refresh_databases(running)
        self._refresh_roles(running)
        self._refresh_connections()

    def _refresh_databases(self, running: bool):
        self.db_table.setRowCount(0)
        if not running:
            return
        databases = self.cluster.databases()
        self.db_table.setRowCount(len(databases))
        for i, db in enumerate(databases):
            self.db_table.setItem(i, 0, QTableWidgetItem(db["name"]))
            size_item = QTableWidgetItem(_human_size(db["size"]))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.db_table.setItem(i, 1, size_item)
            copy_btn = QPushButton("Copy URI")
            copy_btn.setFixedHeight(26)
            dbname = db["name"]
            copy_btn.clicked.connect(lambda checked=False, d=dbname: self._copy_uri(d))
            self.db_table.setCellWidget(i, 2, copy_btn)

    def _refresh_roles(self, running: bool):
        self.roles_table.setRowCount(0)
        if not running:
            return
        roles = self.cluster.roles()
        self.roles_table.setRowCount(len(roles))
        for i, role in enumerate(roles):
            self.roles_table.setItem(i, 0, QTableWidgetItem(role["name"]))
            self.roles_table.setItem(i, 1, QTableWidgetItem("Yes" if role["superuser"] else "No"))
            self.roles_table.setItem(i, 2, QTableWidgetItem("Yes" if role["createdb"] else "No"))
            self.roles_table.setItem(i, 3, QTableWidgetItem("Yes" if role["login"] else "No"))

            # Action menu
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 0, 2, 0)
            action_layout.setSpacing(4)

            pw_btn = QPushButton("Password")
            pw_btn.setFixedHeight(26)
            rname = role["name"]
            pw_btn.clicked.connect(lambda checked=False, n=rname: self._change_password(n))
            action_layout.addWidget(pw_btn)

            drop_btn = QPushButton("Drop")
            drop_btn.setFixedHeight(26)
            drop_btn.clicked.connect(lambda checked=False, n=rname: self._drop_role(n))
            action_layout.addWidget(drop_btn)

            self.roles_table.setCellWidget(i, 4, action_widget)

    def _refresh_connections(self):
        profiles = load_connections()
        self.conn_table.setRowCount(len(profiles))
        for i, p in enumerate(profiles):
            self.conn_table.setItem(i, 0, QTableWidgetItem(p.name))
            self.conn_table.setItem(i, 1, QTableWidgetItem(f"{p.host}:{p.port}"))
            self.conn_table.setItem(i, 2, QTableWidgetItem(p.user))
            self.conn_table.setItem(i, 3, QTableWidgetItem(p.database))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 0, 2, 0)
            action_layout.setSpacing(4)

            copy_btn = QPushButton("Copy URI")
            copy_btn.setFixedHeight(26)
            uri = p.uri()
            copy_btn.clicked.connect(lambda checked=False, u=uri: self._copy_text(u))
            action_layout.addWidget(copy_btn)

            del_btn = QPushButton("Delete")
            del_btn.setFixedHeight(26)
            idx = i
            del_btn.clicked.connect(lambda checked=False, ix=idx: self._delete_connection(ix))
            action_layout.addWidget(del_btn)

            self.conn_table.setCellWidget(i, 4, action_widget)

    # ---- Actions ----

    def _copy_uri(self, dbname: str):
        uri = self.cluster.connection_string(dbname)
        self._copy_text(uri)

    def _copy_text(self, text: str):
        app = QApplication.instance()
        if app:
            app.clipboard().setText(text)

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

    # ---- Role actions ----

    def _create_role(self):
        dialog = CreateRoleDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            ok, msg = self.cluster.create_role(**data)
            if not ok:
                QMessageBox.warning(self, "Create role failed", msg)
            self.refresh()

    def _change_password(self, name: str):
        dialog = ChangePasswordDialog(name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pw = dialog.get_password()
            ok, msg = self.cluster.change_password(name, pw)
            if not ok:
                QMessageBox.warning(self, "Change password failed", msg)
            else:
                QMessageBox.information(self, "Password changed", f"Password updated for {name}.")

    def _drop_role(self, name: str):
        reply = QMessageBox.question(
            self, "Drop role",
            f"Are you sure you want to drop role \"{name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.cluster.drop_role(name)
            if not ok:
                QMessageBox.warning(self, "Drop role failed", msg)
            self.refresh()

    # ---- Connection actions ----

    def _add_connection(self):
        dialog = ConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            profile = dialog.get_profile()
            profiles = load_connections()
            profiles.append(profile)
            save_connections(profiles)
            self._refresh_connections()

    def _delete_connection(self, index: int):
        profiles = load_connections()
        if 0 <= index < len(profiles):
            name = profiles[index].name
            reply = QMessageBox.question(
                self, "Delete connection",
                f"Delete connection \"{name}\"?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                profiles.pop(index)
                save_connections(profiles)
                self._refresh_connections()


# =========================================================================
# Dialogs
# =========================================================================

class CreateRoleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Role")
        self.setMinimumWidth(360)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.superuser_check = QCheckBox()
        self.createdb_check = QCheckBox()

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Password:", self.password_edit)
        layout.addRow("Superuser:", self.superuser_check)
        layout.addRow("Can create DB:", self.createdb_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "password": self.password_edit.text(),
            "superuser": self.superuser_check.isChecked(),
            "createdb": self.createdb_check.isChecked(),
        }


class ChangePasswordDialog(QDialog):
    def __init__(self, role_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change Password — {role_name}")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addRow("New password:", self.password_edit)
        layout.addRow("Confirm:", self.confirm_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self):
        if self.password_edit.text() != self.confirm_edit.text():
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        if not self.password_edit.text():
            QMessageBox.warning(self, "Empty", "Password cannot be empty.")
            return
        self.accept()

    def get_password(self) -> str:
        return self.password_edit.text()


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Connection")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Production, Staging")
        self.host_edit = QLineEdit("localhost")
        self.port_edit = QLineEdit("5432")
        self.user_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.database_edit = QLineEdit("postgres")

        layout.addRow("Profile name:", self.name_edit)
        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_edit)
        layout.addRow("User:", self.user_edit)
        layout.addRow("Password:", self.password_edit)
        layout.addRow("Database:", self.database_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing", "Profile name is required.")
            return
        if not self.user_edit.text().strip():
            QMessageBox.warning(self, "Missing", "User is required.")
            return
        self.accept()

    def get_profile(self) -> ConnectionProfile:
        return ConnectionProfile(
            name=self.name_edit.text().strip(),
            host=self.host_edit.text().strip() or "localhost",
            port=int(self.port_edit.text().strip() or "5432"),
            user=self.user_edit.text().strip(),
            password=self.password_edit.text(),
            database=self.database_edit.text().strip() or "postgres",
        )
