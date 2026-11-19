"""End-to-end lifecycle rehearsal (plan Phase 7 gate, Phase 10 demo check).

One test method = one clean demo run against a fresh temporary database:

citizen registers → submits → second citizen's duplicate is suggested and attached →
admin re-clusters → publishes → match proposed → partner account issued → partner
expresses interest → admin confirms → citizen records resolution feedback → the
published brief is readable publicly.

Two tests run it twice, which is the Phase 10 gate ("two consecutive clean end-to-end
demo runs") in scripted form. It exercises the same endpoints the web client calls;
the browser itself is not driven here.
"""

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

ADMIN_USER = "lifecycle_admin"
ADMIN_PASSWORD = "admin-lifecycle-password-1"
PASSWORD = "citizen-lifecycle-password-1"

REPORTS = (
    "handpump near the primary school has been dry for three months and women walk two kilometres for water",
    "pipe water supply has stopped in ward four since last week",
    "street light on the main road has not worked for two weeks",
    "ration dealer gives seven kilos instead of ten at the end of the month",
    "no doctor has been posted at the primary health centre for two months",
    "school toilet for girls is locked and there is no running water",
    "rural feeder trips every evening and the vaccine fridge stays off",
    "old age pension has not reached the bank account for three cycles",
    "culvert on the block road collapsed and the ambulance cannot pass",
    "mutation file is pending for eleven months at the circle office",
)


class LifecycleDemoTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-lifecycle-")
        database_path = Path(self.temp_dir.name) / "demo.db"
        self.env = patch.dict(
            os.environ,
            {
                "CHALLENGEMAP_DB_PATH": str(database_path),
                "JWT_SECRET": "lifecycle-test-secret-at-least-32-bytes",
                "CHALLENGEMAP_BOOTSTRAP_ADMIN": f"{ADMIN_USER}:{ADMIN_PASSWORD}",
                "CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL": "lifecycle-admin@example.com",
                "DEDUP_THRESHOLD": "0.86",
                "ENV": "test",
                "RATE_LIMIT_ENABLED": "false",
            },
        )
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp_dir.cleanup()

    # --- helpers -----------------------------------------------------------
    def login(self, email: str, password: str, role: str) -> dict:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password, "role": role},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def bearer(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def admin(self) -> dict[str, str]:
        return self.bearer(
            self.login(
                "lifecycle-admin@example.com", ADMIN_PASSWORD, "admin"
            )["access_token"]
        )

    def citizen(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
                "district": "Ranchi",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return self.bearer(
            self.login(f"{username}@example.com", PASSWORD, "citizen")["access_token"]
        )

    def submit(self, headers: dict[str, str], text: str) -> dict:
        response = self.client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "district": "Ranchi",
                "place": "Ward 4",
                "report_text": text,
                "severity": "high",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    # --- the rehearsal -----------------------------------------------------
    def _run_demo_flow(self) -> None:
        alice = self.citizen("alice_lifecycle")
        bob = self.citizen("bob_lifecycle")

        first = self.submit(alice, REPORTS[0])
        for text in REPORTS[1:]:
            self.submit(alice, text)

        duplicate = self.submit(bob, REPORTS[0])
        self.assertTrue(duplicate["duplicate_candidates"])
        candidate = duplicate["duplicate_candidates"][0]
        self.assertEqual(candidate["report_id"], first["report_id"])
        self.assertGreaterEqual(candidate["similarity"], 0.86)

        merged = self.client.post(
            f"/api/v1/complaints/{duplicate['report_id']}/merge",
            headers=bob,
            json={"keep_report_id": first["report_id"]},
        )
        self.assertEqual(merged.status_code, 200, merged.text)
        self.assertEqual(merged.json()["duplicate_of"], first["report_id"])

        # Attaching must not change the report it points at. The background
        # cluster job may already have moved it from "pending" to "clustered".
        target = self.client.get(
            f"/api/v1/complaints/{first['report_id']}", headers=alice
        )
        self.assertEqual(target.status_code, 200)
        self.assertIn(target.json()["status"], {"pending", "clustered"})
        self.assertIsNone(target.json()["duplicate_of"])

        admin = self.admin()
        run = self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        self.assertEqual(run.status_code, 200, run.text)
        self.assertGreater(run.json()["challenges_created"], 0)

        drafts = self.client.get(
            "/api/v1/challenges?status=draft", headers=admin
        ).json()
        self.assertTrue(drafts)
        self.assertEqual(self.client.get("/api/v1/challenges").json(), [])

        published = self.client.post(
            f"/api/v1/challenges/{drafts[0]['id']}/publish", headers=admin
        )
        self.assertEqual(published.status_code, 200, published.text)
        slug = published.json()["slug"]

        brief = self.client.get(f"/api/v1/challenges/{slug}")
        self.assertEqual(brief.status_code, 200, brief.text)
        body = brief.json()
        self.assertTrue(body["evidence"])
        self.assertTrue(body["districts"])
        self.assertTrue(body["timeline"])
        self.assertTrue(body["district_names"])

        matches = self.client.get(f"/api/v1/challenges/{slug}/matches").json()
        self.assertTrue(matches)
        match = matches[0]

        partner_user = f"partner_{uuid.uuid4().hex[:8]}"
        account = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": partner_user,
                "password": PASSWORD,
                "role": "partner",
                "email": f"{partner_user}@example.com",
                "organization_id": match["organization_id"],
            },
        )
        self.assertEqual(account.status_code, 201, account.text)

        partner = self.bearer(
            self.login(f"{partner_user}@example.com", PASSWORD, "partner")["access_token"]
        )
        inbox = self.client.get("/api/v1/partners/me/matches", headers=partner).json()
        self.assertIn(match["id"], [item["id"] for item in inbox])

        interest = self.client.post(
            f"/api/v1/matches/{match['id']}/interest", headers=partner
        )
        self.assertEqual(interest.status_code, 200, interest.text)
        self.assertEqual(interest.json()["status"], "expressed_interest")

        confirmed = self.client.patch(
            f"/api/v1/admin/matches/{match['id']}",
            headers=admin,
            json={"action": "confirm"},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")

        feedback = self.client.post(
            f"/api/v1/complaints/{first['report_id']}/feedback",
            headers=alice,
            json={"status": "Solved", "feedback_text": "water restored after repair"},
        )
        self.assertEqual(feedback.status_code, 201, feedback.text)
        history = self.client.get(
            f"/api/v1/complaints/{first['report_id']}/feedback", headers=alice
        ).json()
        self.assertEqual(history[0]["status"], "Solved")

        public = self.client.get("/api/v1/challenges").json()
        self.assertEqual([item["slug"] for item in public], [slug])

    def test_demo_run_one(self):
        self._run_demo_flow()

    def test_demo_run_two(self):
        self._run_demo_flow()


if __name__ == "__main__":
    unittest.main()
