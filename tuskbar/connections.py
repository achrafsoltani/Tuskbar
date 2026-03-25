"""Connection profile storage — save/load named connections to YAML."""

import base64
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import yaml

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "tuskbar")
CONNECTIONS_FILE = os.path.join(CONFIG_DIR, "connections.yaml")


@dataclass
class ConnectionProfile:
    name: str
    host: str = "localhost"
    port: int = 5432
    user: str = ""
    password: str = ""  # stored base64-encoded in YAML
    database: str = "postgres"

    def uri(self, include_password: bool = True) -> str:
        user_part = quote_plus(self.user) if self.user else ""
        if include_password and self.password:
            user_part += f":{quote_plus(self.password)}"
        if user_part:
            user_part += "@"
        return f"postgresql://{user_part}{self.host}:{self.port}/{self.database}"

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["password"]:
            d["password"] = base64.b64encode(d["password"].encode()).decode()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ConnectionProfile":
        pw = d.get("password", "")
        if pw:
            try:
                pw = base64.b64decode(pw).decode()
            except Exception:
                pass  # not encoded, use as-is
        return cls(
            name=d["name"],
            host=d.get("host", "localhost"),
            port=d.get("port", 5432),
            user=d.get("user", ""),
            password=pw,
            database=d.get("database", "postgres"),
        )


def load_connections() -> list[ConnectionProfile]:
    if not os.path.isfile(CONNECTIONS_FILE):
        return []
    try:
        with open(CONNECTIONS_FILE) as f:
            data = yaml.safe_load(f)
        if not data or not isinstance(data, list):
            return []
        return [ConnectionProfile.from_dict(d) for d in data]
    except Exception:
        return []


def save_connections(profiles: list[ConnectionProfile]):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = [p.to_dict() for p in profiles]
    with open(CONNECTIONS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    # Restrict permissions — contains encoded passwords
    os.chmod(CONNECTIONS_FILE, 0o600)
