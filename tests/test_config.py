import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.config import load_env_file

KEYS = ("CHALLENGEMAP_TEST_QUOTED", "CHALLENGEMAP_TEST_PLAIN", "CHALLENGEMAP_TEST_EXPORT", "CHALLENGEMAP_TEST_EMPTY")


class EnvFileTests(unittest.TestCase):
    def test_missing_file_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_env_file(Path(tmp) / "missing.env"), 0)

    def test_values_load_and_explicit_environment_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "[TEMPLATE]",
                        "# a comment",
                        "",
                        'CHALLENGEMAP_TEST_QUOTED="quoted value"',
                        "CHALLENGEMAP_TEST_PLAIN=plain",
                        "export CHALLENGEMAP_TEST_EXPORT=3",
                        "CHALLENGEMAP_TEST_EMPTY=",
                        "broken line without equals",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=False):
                for key in KEYS:
                    os.environ.pop(key, None)

                loaded = load_env_file(path)

                self.assertEqual(loaded, 4)
                self.assertEqual(os.environ["CHALLENGEMAP_TEST_QUOTED"], "quoted value")
                self.assertEqual(os.environ["CHALLENGEMAP_TEST_PLAIN"], "plain")
                self.assertEqual(os.environ["CHALLENGEMAP_TEST_EXPORT"], "3")
                self.assertEqual(os.environ["CHALLENGEMAP_TEST_EMPTY"], "")

                # Already-set keys are skipped, so a second load sets nothing.
                os.environ["CHALLENGEMAP_TEST_QUOTED"] = "explicit"
                self.assertEqual(load_env_file(path), 0)
                self.assertEqual(os.environ["CHALLENGEMAP_TEST_QUOTED"], "explicit")


if __name__ == "__main__":
    unittest.main()
