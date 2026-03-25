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

    def start(self) -> tuple[bool, str]:
        result = subprocess.run(
            [self._bin("pg_ctl"), "-D", self.data_dir, "-l",
             os.path.join(self.data_dir, "server.log"),
             "-o", f"-p {self.port}",
             "start"],
            capture_output=True, text=True,
        )
        return result.returncode == 0, result.stderr or result.stdout

    def stop(self) -> tuple[bool, str]:
        result = subprocess.run(
            [self._bin("pg_ctl"), "-D", self.data_dir, "stop"],
            capture_output=True, text=True,
        )
        return result.returncode == 0, result.stderr or result.stdout

    def restart(self) -> tuple[bool, str]:
        result = subprocess.run(
            [self._bin("pg_ctl"), "-D", self.data_dir,
             "-o", f"-p {self.port}",
             "restart"],
            capture_output=True, text=True,
        )
        return result.returncode == 0, result.stderr or result.stdout

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
        return f"postgresql://{self.host}:{self.port}/{dbname}"


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
