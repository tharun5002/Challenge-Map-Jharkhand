import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.backup_db import backup_database, restore_database


class BackupDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-backup-")
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "source.db"
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "CREATE TABLE complaints (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO complaints VALUES ('C-1', 'handpump dry')"
            )
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def rows(self, path: Path) -> list[tuple[str, str]]:
        with closing(sqlite3.connect(path)) as connection:
            return connection.execute("SELECT id, body FROM complaints").fetchall()

    def test_backup_is_a_consistent_copy(self):
        output = self.root / "copy.db"
        result = backup_database(self.database, output)

        self.assertEqual(result, output.resolve())
        self.assertEqual(self.rows(output), [("C-1", "handpump dry")])
        self.assertEqual(self.rows(self.database), [("C-1", "handpump dry")])

    def test_restore_requires_force_and_replaces_data(self):
        output = self.root / "copy.db"
        backup_database(self.database, output)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DELETE FROM complaints")
            connection.execute("INSERT INTO complaints VALUES ('C-2', 'later edit')")
            connection.commit()

        with self.assertRaises(FileExistsError):
            restore_database(output, self.database)

        restore_database(output, self.database, overwrite=True)
        self.assertEqual(self.rows(self.database), [("C-1", "handpump dry")])

    def test_missing_database_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            backup_database(self.root / "missing.db", self.root / "copy.db")


if __name__ == "__main__":
    unittest.main()
