"""SQLite persistence for the API.

Phase 2 replaces this store with PostgreSQL + SQLAlchemy + Alembic. Until a
Postgres instance exists, every statement lives behind this module so that swap
stays local instead of leaking SQL into the routers.

What is deliberately *not* here: the pgvector embedding column and the
``challenges`` rows derived from the 15k corpus. Both need the Phase 2 schema.
Complaints submitted through the API are real rows in this database, and their
``is_synthetic`` flag is always 0.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.config import get_settings
from api.security import hash_password

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    email TEXT COLLATE NOCASE,
    role TEXT NOT NULL DEFAULT 'citizen'
        CHECK (role IN ('citizen', 'partner', 'admin')),
    district TEXT,
    organization_id INTEGER,
    requested_organization_name TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    approval_pending INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

def users_table_ddl(name: str = "users") -> str:
    """Return the users DDL under another table name (migration rebuild)."""
    return USERS_TABLE.replace(
        "CREATE TABLE IF NOT EXISTS users (", f"CREATE TABLE {name} (", 1
    )


SCHEMA = (
    USERS_TABLE
    + """;
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_digest TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL UNIQUE,
    owner_id INTEGER REFERENCES users(id),
    district TEXT NOT NULL,
    place TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    severity TEXT NOT NULL DEFAULT 'unknown'
        CHECK (severity IN ('unknown', 'low', 'medium', 'high', 'critical')),
    affected_population INTEGER,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'clustered', 'merged', 'rejected')),
    duplicate_of TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    reported_on TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT 'unassigned',
    capability_tags TEXT NOT NULL DEFAULT '[]',
    complaint_count INTEGER NOT NULL DEFAULT 0,
    affected_total INTEGER NOT NULL DEFAULT 0,
    severity_score REAL NOT NULL DEFAULT 0,
    priority_score REAL NOT NULL DEFAULT 0,
    priority_breakdown TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'under_review', 'published', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT
);
CREATE TABLE IF NOT EXISTS challenge_complaints (
    challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    complaint_report_id TEXT NOT NULL,
    similarity REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (challenge_id, complaint_report_id)
);
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    org_type TEXT NOT NULL,
    capability_tags TEXT NOT NULL DEFAULT '[]',
    districts TEXT NOT NULL DEFAULT '[]',
    capacity REAL NOT NULL DEFAULT 0.5,
    contact_email TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    score REAL NOT NULL,
    breakdown TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN ('suggested', 'confirmed', 'declined', 'expressed_interest')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (challenge_id, organization_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES complaints(report_id) ON DELETE CASCADE,
    status TEXT NOT NULL
        CHECK (status IN ('Not solved', 'Partially solved', 'Solved')),
    feedback_text TEXT NOT NULL DEFAULT '',
    submitted_by INTEGER REFERENCES users(id),
    submitted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES complaints(report_id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL
        CHECK (status IN ('acknowledged', 'in_progress', 'resolved', 'unable_to_resolve')),
    response_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
    ON users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_complaints_district ON complaints(district);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status, reported_on);
CREATE INDEX IF NOT EXISTS idx_feedback_report ON feedback(report_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_staff_responses_report
    ON staff_responses(report_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_matches_org ON matches(organization_id, status);
"""
)

# Demo directory rows. They are not real partnerships; the API labels them demo in
# api/README.md and the UI already badges synthetic content.
DEMO_ORGANIZATIONS: tuple[tuple[str, str, list[str], list[str], float], ...] = (
    ("BIT Mesra - Civil Engineering", "university_dept", ["water", "roads", "sanitation"], ["Ranchi", "Khunti", "Ramgarh"], 0.9),
    ("XISS Ranchi - Social Research", "university_dept", ["welfare", "employment", "food"], ["Ranchi", "Simdega", "Gumla"], 0.8),
    ("IIT (ISM) Dhanbad - Energy Group", "research_lab", ["electricity", "safety"], ["Dhanbad", "Bokaro", "Giridih"], 0.85),
    ("Birsa Agricultural University", "university_dept", ["agriculture", "food"], ["Ranchi", "Palamu", "Chatra"], 0.75),
    ("Jan Swasthya Sahyog", "ngo", ["health", "sanitation"], ["Palamu", "Garhwa", "Latehar"], 0.7),
    ("Pratham Jharkhand", "ngo", ["education", "welfare"], ["Dumka", "Godda", "Sahibganj"], 0.65),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_report_id() -> str:
    return str(uuid.uuid4())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "challenge"


@contextmanager
def connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    target = path or get_settings().database_path
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rebuild_users_for_partner_role(conn: sqlite3.Connection) -> None:
    """Extend a legacy users table whose CHECK allows only citizen/admin.

    SQLite cannot alter a CHECK constraint in place. The legacy file is scheduled
    for deletion once Phase 2 imports it, so a rebuild is preferable to leaving
    the ``partner`` role impossible to store.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if row is None or "partner" in (row["sql"] or "").lower():
        return
    # Build the replacement under a different name and swap it in. Renaming the
    # old table would make SQLite rewrite every child reference
    # (challenge_reports.owner_id, ...) to point at the renamed table, leaving
    # the database referring to a table that no longer exists. Dropping the old
    # table leaves those references spelling "users", which the replacement
    # satisfies again.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS users_rebuilt")
        conn.execute(users_table_ddl("users_rebuilt"))
        conn.execute(
            """
            INSERT INTO users_rebuilt (
                id, username, password_salt, password_hash, full_name, role,
                district, organization_id, is_active, created_at, updated_at
            )
            SELECT id, username, password_salt, password_hash, '',
                   CASE WHEN role IN ('citizen', 'partner', 'admin') THEN role
                        ELSE 'citizen' END,
                   NULL, NULL, 1, created_at, ?
            FROM users
            """,
            (utc_now(),),
        )
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_rebuilt RENAME TO users")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _ensure_user_email_column(conn: sqlite3.Connection) -> None:
    """Add ``users.email`` to a database created before accounts had one."""
    if not _table_exists(conn, "users"):
        return
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" in columns:
        return
    conn.execute("ALTER TABLE users ADD COLUMN email TEXT COLLATE NOCASE")


def _ensure_partner_application_columns(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "users"):
        return
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    additions = {
        "requested_organization_name": "TEXT NOT NULL DEFAULT ''",
        "job_title": "TEXT NOT NULL DEFAULT ''",
        "approval_pending": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")


def init_db(path: Path | None = None) -> None:
    with connection(path) as conn:
        if _table_exists(conn, "users") and not _table_exists(conn, "complaints"):
            _rebuild_users_for_partner_role(conn)
        # Runs before the script: SCHEMA indexes users(email), which an older
        # database would not have yet.
        _ensure_user_email_column(conn)
        _ensure_partner_application_columns(conn)
        conn.executescript(SCHEMA)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def create_user(
    username: str,
    password: str,
    *,
    role: str = "citizen",
    full_name: str = "",
    email: str | None = None,
    district: str | None = None,
    organization_id: int | None = None,
    requested_organization_name: str = "",
    job_title: str = "",
    approval_pending: bool = False,
    is_active: bool = True,
) -> int:
    salt, hashed = hash_password(password)
    now = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (
                username, password_salt, password_hash, full_name, email, role,
                district, organization_id, requested_organization_name, job_title,
                approval_pending, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                salt,
                hashed,
                full_name,
                email,
                role,
                district,
                organization_id,
                requested_organization_name,
                job_title,
                int(approval_pending),
                int(is_active),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def update_user_password(user_id: int, salt: str, hashed: str) -> None:
    """Replace a user's stored password digest (used to upgrade PBKDF2 → Argon2id)."""
    with connection() as conn:
        conn.execute(
            "UPDATE users SET password_salt = ?, password_hash = ?, updated_at = ? "
            "WHERE id = ?",
            (salt, hashed, utc_now(), user_id),
        )


def ensure_bootstrap_admin(spec: str | None, email: str | None = None) -> None:
    """Create or promote the admin named in CHALLENGEMAP_BOOTSTRAP_ADMIN.

    The spec is ``username:password``. ``email`` (from
    CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL) is required for email-based login and
    applied on every startup without resetting the password.
    """
    if not spec or ":" not in spec:
        return
    username, password = spec.split(":", 1)
    username = username.strip()
    if not username or not password:
        return
    email = (email or "").strip() or None
    with connection() as conn:
        exists = conn.execute(
            "SELECT id, email FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if exists:
            if email is None and not exists["email"]:
                raise RuntimeError(
                    "CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL is required for the "
                    "bootstrap administrator to sign in."
                )
            conn.execute(
                "UPDATE users SET role = 'admin', email = COALESCE(?, email), "
                "updated_at = ? WHERE id = ?",
                (email, utc_now(), int(exists["id"])),
            )
            return
    if email is None:
        raise RuntimeError(
            "CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL is required to create the "
            "bootstrap administrator."
        )
    try:
        create_user(
            username,
            password,
            role="admin",
            full_name="Bootstrap admin",
            email=email,
        )
    except sqlite3.IntegrityError as error:
        raise RuntimeError(
            "Could not create the bootstrap administrator. Check that its "
            "username and email are not already assigned to another account."
        ) from error


def seed_organizations() -> None:
    with connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM organizations").fetchone()["n"]
        if count:
            return
        now = utc_now()
        for name, org_type, tags, districts, capacity in DEMO_ORGANIZATIONS:
            conn.execute(
                """
                INSERT INTO organizations (
                    name, org_type, capability_tags, districts, capacity,
                    contact_email, created_at
                ) VALUES (?, ?, ?, ?, ?, '', ?)
                """,
                (
                    name,
                    org_type,
                    json.dumps(tags),
                    json.dumps(districts),
                    capacity,
                    now,
                ),
            )


def audit(
    conn: sqlite3.Connection,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (actor_id, action, entity_type, entity_id, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            action,
            entity_type,
            None if entity_id is None else str(entity_id),
            json.dumps(payload or {}),
            utc_now(),
        ),
    )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}
