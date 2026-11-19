"""Runtime configuration for the API, read fresh from the environment.

Nothing is cached: tests (and deployments) switch database paths and secrets by
setting variables, and a cached settings object would silently keep the old one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "challenge_map.db"
DEVELOPMENT_SECRET = "development-only-insecure-secret"


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret: str
    access_ttl_minutes: int
    refresh_ttl_days: int
    dedup_threshold: float
    allowed_origins: tuple[str, ...]
    bootstrap_admin: str | None
    bootstrap_admin_email: str | None
    env: str


def load_env_file(path: Path | None = None) -> int:
    """Load ``KEY=VALUE`` pairs from a dotenv file into the process environment.

    Dependency-free on purpose: the project already ships a venv-based setup and
    a single parsing rule (split on the first ``=``, strip optional quotes,
    ignore comments and malformed lines). Real environment variables always win,
    so a deployment that sets ``JWT_SECRET`` is never overridden by a stray file.
    Returns the number of variables actually set.
    """
    target = path or PROJECT_ROOT / ".env"
    if not target.exists():
        return 0

    loaded = 0
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def get_settings() -> Settings:
    env = os.environ.get("ENV", "development")
    secret = os.environ.get("JWT_SECRET", DEVELOPMENT_SECRET)
    if env == "production" and secret == DEVELOPMENT_SECRET:
        raise RuntimeError(
            "JWT_SECRET must be set to a private value when ENV=production."
        )
    return Settings(
        database_path=Path(
            os.environ.get("CHALLENGEMAP_DB_PATH", str(DEFAULT_DB_PATH))
        ).expanduser(),
        jwt_secret=secret,
        access_ttl_minutes=int(os.environ.get("JWT_TTL_MINUTES", "60")),
        refresh_ttl_days=int(os.environ.get("JWT_REFRESH_TTL_DAYS", "7")),
        dedup_threshold=float(os.environ.get("DEDUP_THRESHOLD", "0.86")),
        allowed_origins=_split(
            os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
        ),
        bootstrap_admin=os.environ.get("CHALLENGEMAP_BOOTSTRAP_ADMIN"),
        bootstrap_admin_email=os.environ.get("CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL"),
        env=env,
    )
