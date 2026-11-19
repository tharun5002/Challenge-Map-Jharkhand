"""Online SQLite backup and restore for the ChallengeMap store.

The API persists to SQLite until Phase 2 (PostgreSQL + pgvector). This is the
local half of the Phase 8 backup/restore drill: SQLite's backup API takes a
consistent copy even while the service is running, both sides are checked with
``PRAGMA integrity_check``, and restore refuses to replace a database unless
``--force`` is passed. It does not exercise ``pg_dump`` or a managed snapshot.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import get_settings, load_env_file


def _integrity_ok(path: Path) -> bool:
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    return bool(row) and row[0] == "ok"


def backup_database(database: Path, output: Path, *, overwrite: bool = False) -> Path:
    """Copy ``database`` to ``output`` and verify the copy."""
    database = database.resolve()
    output = output.resolve()
    if not database.exists():
        raise FileNotFoundError(f"database not found: {database}")
    if output.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {output}; pass --force")

    output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as source, closing(
        sqlite3.connect(output)
    ) as destination:
        source.backup(destination)

    if not _integrity_ok(output):
        output.unlink(missing_ok=True)
        raise RuntimeError("backup failed PRAGMA integrity_check; partial file removed")
    return output


def restore_database(backup: Path, database: Path, *, overwrite: bool = False) -> Path:
    """Replace ``database`` with ``backup`` after verifying the backup."""
    backup = backup.resolve()
    database = database.resolve()
    if not backup.exists():
        raise FileNotFoundError(f"backup not found: {backup}")
    if not _integrity_ok(backup):
        raise RuntimeError(f"{backup} failed PRAGMA integrity_check")
    if database.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {database}; pass --force")

    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(backup)) as source, closing(
        sqlite3.connect(database)
    ) as destination:
        source.backup(destination)

    if not _integrity_ok(database):
        raise RuntimeError("restored database failed PRAGMA integrity_check")
    return database


def _default_output(database: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return PROJECT_ROOT / "backups" / f"{database.stem}-{stamp}.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back up or restore the local ChallengeMap SQLite database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="Database to back up (default: the configured store).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Backup path. Defaults to backups/<name>-<timestamp>.db.",
    )
    parser.add_argument(
        "--restore",
        type=Path,
        help="Restore this backup into --database instead of taking a backup.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing backup or database.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file()
    database = (args.database or get_settings().database_path).expanduser()

    try:
        if args.restore:
            restore_database(args.restore, database, overwrite=args.force)
            print(f"Restored {database} from {args.restore} (integrity ok).")
        else:
            output = args.output or _default_output(database)
            backup_database(database, output, overwrite=args.force)
            print(f"Backed up {database} to {output} (integrity ok).")
    except (FileNotFoundError, FileExistsError, RuntimeError, sqlite3.Error) as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
