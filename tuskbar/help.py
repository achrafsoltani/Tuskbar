"""Help & About dialog for Tuskbar."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout, QWidget

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

HELP_HTML = """
<h2>Tuskbar — PostgreSQL Manager</h2>
<p style="color: #888;">Version 0.1.0</p>

<h3>Getting Started</h3>
<p>Tuskbar is a system tray application for managing PostgreSQL on Linux.
It auto-detects your PostgreSQL installation and lets you control it from the tray.</p>

<h3>System Tray</h3>
<ul>
  <li><b>Click</b> the tray icon to open the dashboard</li>
  <li>The icon changes colour based on server status:
    <ul>
      <li><span style="color: #4caf50;">●</span> <b>Green dot</b> — PostgreSQL is running</li>
      <li><span style="color: #ef5350;">●</span> <b>Red dot</b> — PostgreSQL is stopped</li>
      <li><span style="color: #808080;">●</span> <b>Grey</b> — status unknown</li>
    </ul>
  </li>
  <li>Status is polled every 5 seconds automatically</li>
</ul>

<h3>Dashboard</h3>
<ul>
  <li><b>Start / Stop / Restart</b> — controls the PostgreSQL service via <code>systemctl</code>.
      You will be prompted for your password (polkit authentication).</li>
  <li><b>Open psql</b> — opens a terminal with <code>psql</code> connected to the selected database
      (or <code>postgres</code> by default)</li>
  <li><b>Copy URI</b> — copies the connection string to clipboard
      (e.g. <code>postgresql://localhost:5432/mydb</code>)</li>
  <li><b>Database list</b> — shows all non-template databases with their size</li>
</ul>

<h3>Permissions</h3>
<p>Tuskbar runs as your user. Server control (start/stop/restart) requires elevated
privileges because PostgreSQL runs as the <code>postgres</code> system user.</p>
<ul>
  <li><b>System-managed PostgreSQL</b> (installed via apt/dnf): uses
      <code>pkexec systemctl start|stop|restart postgresql</code> — you'll see a
      graphical password prompt from your desktop's polkit agent.</li>
  <li><b>User-managed PostgreSQL</b> (custom data dir): uses <code>pg_ctl</code> directly,
      no elevated privileges needed.</li>
</ul>
<p>Database listing and psql use <b>peer authentication</b> over Unix sockets.
Your Unix user must have a matching PostgreSQL role. To create one:</p>
<pre>sudo -u postgres createuser --superuser YOUR_USERNAME</pre>

<h3>Installing PostgreSQL</h3>

<p><b>Debian / Ubuntu:</b></p>
<pre>sudo apt install postgresql postgresql-client</pre>

<p><b>Fedora / RHEL:</b></p>
<pre>sudo dnf install postgresql-server postgresql
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql</pre>

<p><b>Arch Linux:</b></p>
<pre>sudo pacman -S postgresql
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl enable --now postgresql</pre>

<p>After installation, create a role for your user:</p>
<pre>sudo -u postgres createuser --superuser $(whoami)</pre>

<h3>Troubleshooting</h3>

<p><b>Tray icon not visible:</b><br/>
On GNOME, install the
<a href="https://extensions.gnome.org/extension/615/appindicator-support/">AppIndicator extension</a>.
KDE Plasma supports tray icons natively.</p>

<p><b>"Could not detect PostgreSQL data directory":</b><br/>
Set the <code>PGDATA</code> environment variable to your data directory, e.g.:<br/>
<code>export PGDATA=/var/lib/postgresql/16/main</code></p>

<p><b>Database list is empty:</b><br/>
Ensure PostgreSQL is running and your user has a PostgreSQL role (see Permissions above).</p>

<p><b>Start/Stop fails:</b><br/>
If you see a permission error, ensure polkit is running. On minimal installs,
you may need <code>polkit-kde-agent</code> (KDE) or <code>polkit-gnome</code> (GNOME).</p>

<p><b>psql terminal closes immediately:</b><br/>
Your user likely doesn't have a PostgreSQL role. Run:<br/>
<code>sudo -u postgres createuser --superuser $(whoami)</code></p>

<hr/>
<p style="color: #888;">
  <a href="https://github.com/AchrafSoltani/Tuskbar">GitHub</a> ·
  MIT License · Achraf Soltani
</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tuskbar — Help")
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "tuskbar-window.svg")))
        self.setMinimumSize(520, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)

        label = QLabel(HELP_HTML)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        label.setFont(QFont("", 10))

        content_layout.addWidget(label)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
