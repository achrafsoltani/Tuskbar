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
            import psycopg
            with psycopg.connect(
                host=self.host, port=self.port, dbname="postgres",
                autocommit=True,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT d.datname, pg_database_size(d.datname) AS size
                        FROM pg_database d
                        WHERE d.datistemplate = false
                        ORDER BY d.datname
                    """)
                    return [
                        {"name": row[0], "size": row[1]}
                        for row in cur.fetchall()
                    ]
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

    # Common Linux locations
    candidates = [
        os.path.expanduser("~/.local/share/postgresql"),
        "/var/lib/postgresql/data",
    ]

    # Check for versioned dirs under /var/lib/postgresql
    pg_base = Path("/var/lib/postgresql")
    if pg_base.is_dir():
        for child in sorted(pg_base.iterdir(), reverse=True):
            main = child / "main"
            if main.is_dir():
                candidates.insert(0, str(main))

    for path in candidates:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "PG_VERSION")):
            return path

    return ""
