"""PostgreSQL server control and introspection via pg_ctl / pg_isready / psql."""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PgCluster:
    """Represents a single PostgreSQL cluster."""
    data_dir: str
    port: int = 5432
    host: str = "localhost"
    bindir: str = ""

    def __post_init__(self):
        if not self.bindir:
            self.bindir = self._detect_bindir()

    def _detect_bindir(self) -> str:
        pg_config = shutil.which("pg_config")
        if pg_config:
            result = subprocess.run(
                [pg_config, "--bindir"], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        return ""

    def _bin(self, name: str) -> str:
        if self.bindir:
            path = os.path.join(self.bindir, name)
            if os.path.isfile(path):
                return path
        return shutil.which(name) or name

    def status(self) -> str:
        """Return 'running', 'stopped', or 'error'."""
        result = subprocess.run(
            [self._bin("pg_isready"), "-h", self.host, "-p", str(self.port)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "running"
        if result.returncode == 2:
            return "stopped"
        return "error"

    def _systemctl_available(self) -> bool:
        """Check if PostgreSQL is managed by systemd."""
        result = subprocess.run(
            ["systemctl", "is-enabled", "postgresql"],
            capture_output=True, text=True,
        )
        return result.returncode == 0 or result.stdout.strip() == "disabled"

    def autostart_enabled(self) -> bool | None:
        """Check if PostgreSQL is enabled to start on boot.
        Returns None if not managed by systemd."""
        result = subprocess.run(
            ["systemctl", "is-enabled", "postgresql"],
            capture_output=True, text=True,
        )
        status = result.stdout.strip()
        if status == "enabled":
            return True
        if status == "disabled":
            return False
        return None

    def set_autostart(self, enabled: bool) -> tuple[bool, str]:
        """Enable or disable PostgreSQL autostart via systemctl."""
        action = "enable" if enabled else "disable"
        result = subprocess.run(
            ["pkexec", "systemctl", action, "postgresql"],
            capture_output=True, text=True,
        )
        return result.returncode == 0, result.stderr or result.stdout

    def _run_control(self, action: str) -> tuple[bool, str]:
        """Start/stop/restart PostgreSQL via systemctl (with pkexec for auth)
        or pg_ctl as fallback."""
        if self._systemctl_available():
            result = subprocess.run(
                ["pkexec", "systemctl", action, "postgresql"],
                capture_output=True, text=True,
            )
        else:
            args = [self._bin("pg_ctl"), "-D", self.data_dir]
            if action in ("start", "restart"):
                args += ["-l", os.path.join(self.data_dir, "server.log"),
                         "-o", f"-p {self.port}"]
            args.append(action)
            result = subprocess.run(args, capture_output=True, text=True)
        return result.returncode == 0, result.stderr or result.stdout

    def start(self) -> tuple[bool, str]:
        return self._run_control("start")

    def stop(self) -> tuple[bool, str]:
        return self._run_control("stop")

    def restart(self) -> tuple[bool, str]:
        return self._run_control("restart")

    def version(self) -> str:
        result = subprocess.run(
            [self._bin("psql"), "--version"], capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"

    def databases(self) -> list[dict]:
        """List databases with name and size."""
        try:
            query = (
                "SELECT datname, pg_database_size(datname) "
                "FROM pg_database WHERE datistemplate = false ORDER BY datname;"
            )
            result = subprocess.run(
                [self._bin("psql"), "-p", str(self.port), "-d", "postgres",
                 "-tAF|", "-c", query],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return []
            databases = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("|")
                if len(parts) == 2:
                    databases.append({"name": parts[0], "size": int(parts[1])})
            return databases
        except Exception:
            return []

    def connection_string(self, dbname: str = "postgres") -> str:
        import getpass
        user = getpass.getuser()
        return f"postgresql://{user}@{self.host}:{self.port}/{dbname}"

    # --- Role management ---

    def _psql_query(self, query: str) -> str | None:
        """Run a psql query and return raw stdout, or None on failure."""
        try:
            result = subprocess.run(
                [self._bin("psql"), "-p", str(self.port), "-d", "postgres",
                 "-tAF|", "-c", query],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _psql_exec(self, query: str) -> tuple[bool, str]:
        """Execute a psql command (no result set expected)."""
        try:
            result = subprocess.run(
                [self._bin("psql"), "-p", str(self.port), "-d", "postgres",
                 "-c", query],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0, result.stderr or result.stdout
        except Exception as e:
            return False, str(e)

    def roles(self) -> list[dict]:
        """List PostgreSQL roles with attributes."""
        out = self._psql_query(
            "SELECT rolname, rolsuper, rolcreatedb, rolcanlogin "
            "FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY rolname;"
        )
        if not out:
            return []
        roles = []
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) == 4:
                roles.append({
                    "name": parts[0],
                    "superuser": parts[1] == "t",
                    "createdb": parts[2] == "t",
                    "login": parts[3] == "t",
                })
        return roles

    def create_role(self, name: str, password: str,
                    superuser: bool = False, createdb: bool = False) -> tuple[bool, str]:
        """Create a new PostgreSQL role."""
        opts = []
        opts.append("SUPERUSER" if superuser else "NOSUPERUSER")
        opts.append("CREATEDB" if createdb else "NOCREATEDB")
        opts.append("LOGIN")
        # Escape single quotes in password
        safe_pw = password.replace("'", "''")
        safe_name = name.replace('"', '""')
        query = f'CREATE ROLE "{safe_name}" WITH {" ".join(opts)} PASSWORD \'{safe_pw}\';'
        return self._psql_exec(query)

    def change_password(self, name: str, password: str) -> tuple[bool, str]:
        """Change password for an existing role."""
        safe_pw = password.replace("'", "''")
        safe_name = name.replace('"', '""')
        query = f'ALTER ROLE "{safe_name}" PASSWORD \'{safe_pw}\';'
        return self._psql_exec(query)

    def drop_role(self, name: str) -> tuple[bool, str]:
        """Drop a PostgreSQL role."""
        safe_name = name.replace('"', '""')
        query = f'DROP ROLE "{safe_name}";'
        return self._psql_exec(query)


def detect_data_dir() -> str:
    """Try to find the default PostgreSQL data directory."""
    # Check PGDATA env var
    pgdata = os.environ.get("PGDATA")
    if pgdata and os.path.isdir(pgdata):
        return pgdata

    # Ask a running server directly
    try:
        result = subprocess.run(
            ["psql", "-d", "postgres", "-tAc", "SHOW data_directory;"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            if os.path.isdir(path):
                return path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Common Linux locations
    candidates = [
        os.path.expanduser("~/.local/share/postgresql"),
        "/var/lib/postgresql/data",
    ]

    # Check for versioned dirs under /var/lib/postgresql
    pg_base = Path("/var/lib/postgresql")
    try:
        if pg_base.is_dir():
            for child in sorted(pg_base.iterdir(), reverse=True):
                main = child / "main"
                candidates.insert(0, str(main))
    except PermissionError:
        # Debian/Ubuntu: dirs owned by postgres user, guess versioned paths
        for ver in range(20, 13, -1):
            candidates.insert(0, f"/var/lib/postgresql/{ver}/main")

    for path in candidates:
        if os.path.isdir(path):
            return path

    return ""
