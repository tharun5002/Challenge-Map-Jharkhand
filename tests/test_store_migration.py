import sqlite3
import tempfile
import unittest
from pathlib import Path

from api.store import init_db


class LegacyDatabaseMigrationTests(unittest.TestCase):
    """The store must upgrade the pre-Phase-5 database without breaking FKs."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-migration-")
        self.path = Path(self.temp_dir.name) / "legacy.db"
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'citizen'
                        CHECK (role IN ('citizen', 'admin')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE challenge_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT UNIQUE NOT NULL,
                    owner_id INTEGER REFERENCES users(id)
                );
                CREATE TABLE complaint_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL,
                    submitted_by INTEGER REFERENCES users(id)
                );
                INSERT INTO users (username, password_salt, password_hash, role, created_at)
                VALUES ('legacy_user', 'aabb', 'ccdd', 'admin', '2026-01-01T00:00:00');
                INSERT INTO challenge_reports (report_id, owner_id) VALUES ('r-1', 1);
                INSERT INTO complaint_feedback (report_id, submitted_by) VALUES ('r-1', 1);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _read(self):
        conn = sqlite3.connect(self.path)
        try:
            return {
                "users_sql": conn.execute(
                    "SELECT sql FROM sqlite_master WHERE name = 'users'"
                ).fetchone()[0],
                "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "role": conn.execute(
                    "SELECT role FROM users WHERE username = 'legacy_user'"
                ).fetchone()[0],
                "fk_violations": conn.execute("PRAGMA foreign_key_check").fetchall(),
                "tables": [
                    row[0] for row in conn.execute("SELECT name FROM sqlite_master")
                ],
            }
        finally:
            conn.close()

    def test_rebuild_allows_partner_role_and_preserves_rows(self):
        init_db(self.path)
        state = self._read()
        self.assertIn("'partner'", state["users_sql"])
        self.assertEqual(state["users"], 1)
        self.assertEqual(state["role"], "admin")
        self.assertEqual(state["fk_violations"], [])
        # The scratch table must be gone: it was renamed into place.
        self.assertNotIn("users_rebuilt", state["tables"])
        self.assertNotIn("users_legacy", state["tables"])
        self.assertIn("challenge_reports", state["tables"])

    def test_migration_is_idempotent(self):
        init_db(self.path)
        init_db(self.path)
        state = self._read()
        self.assertEqual(state["users"], 1)
        self.assertEqual(state["fk_violations"], [])


if __name__ == "__main__":
    unittest.main()
