import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import create_app
from api.rate_limit import LOGIN_LIMIT, limiter


class RateLimitTests(unittest.TestCase):
    """The limiter is off for the rest of the suite; here it is switched on."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-limits-")
        self.env = patch.dict(
            os.environ,
            {
                "CHALLENGEMAP_DB_PATH": str(
                    Path(self.temp_dir.name) / "limits.db"
                ),
                "JWT_SECRET": "unit-test-secret",
                "ENV": "test",
            },
        )
        self.env.start()
        limiter.reset()
        limiter.enabled = True
        self.addCleanup(self._disable)
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def _disable(self):
        limiter.enabled = False
        limiter.reset()
        self.env.stop()
        self.temp_dir.cleanup()

    def test_login_returns_429_after_the_configured_budget(self):
        allowed = int(LOGIN_LIMIT.split("/")[0])
        body = {
            "email": "no-such-user@example.com",
            "password": "definitely-wrong",
            "role": "citizen",
        }

        for attempt in range(allowed):
            response = self.client.post("/api/v1/auth/login", json=body)
            self.assertEqual(
                response.status_code,
                401,
                f"attempt {attempt + 1} of {allowed} should still be allowed",
            )

        blocked = self.client.post("/api/v1/auth/login", json=body)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Rate limit exceeded", blocked.text)

    def test_limits_are_scoped_to_the_decorated_route(self):
        """Exhausting login must not block an unrelated public endpoint."""
        body = {
            "email": "no-such-user@example.com",
            "password": "definitely-wrong",
            "role": "citizen",
        }
        for _ in range(int(LOGIN_LIMIT.split("/")[0])):
            self.client.post("/api/v1/auth/login", json=body)

        self.assertEqual(self.client.post("/api/v1/auth/login", json=body).status_code, 429)
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
