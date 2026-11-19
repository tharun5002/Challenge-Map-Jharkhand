import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


class ChallengeMapApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-api-test-")
        database_path = Path(self.temp_dir.name) / "challenge_map.db"
        self.database_override = patch.dict(
            os.environ,
            {"CHALLENGEMAP_DB_PATH": str(database_path)},
        )
        self.database_override.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.database_override.stop()
        self.temp_dir.cleanup()

    def register(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "a-secure-test-password",
                "password_confirmation": "a-secure-test-password",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return {
            "username": username,
            "email": f"{username}@example.com",
            "password": "a-secure-test-password",
        }

    def test_health_and_citizen_registration(self):
        health = self.client.get("/api/v1/health").json()
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["database"], "ok")
        citizen = self.register("citizen_one")
        response = self.client.get("/api/v1/me", auth=(citizen["email"], citizen["password"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "citizen_one")
        self.assertEqual(response.json()["role"], "citizen")
        username_auth = self.client.get(
            "/api/v1/me", auth=(citizen["username"], citizen["password"])
        )
        self.assertEqual(username_auth.status_code, 401)

    def test_password_whitespace_is_preserved(self):
        password = "  a-secure-test-password  "
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "space_user",
                "email": "space-user@example.com",
                "password": password,
                "password_confirmation": password,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            self.client.get("/api/v1/me", auth=("space-user@example.com", password)).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/me",
                auth=("space-user@example.com", password.strip()),
            ).status_code,
            401,
        )

    def test_complaint_and_feedback_are_persisted_for_owner(self):
        citizen = self.register("reporter_one")
        auth = (citizen["email"], citizen["password"])
        complaint_response = self.client.post(
            "/api/v1/complaints",
            auth=auth,
            json={
                "district": "ranchi",
                "place": "  Morabadi   ",
                "report_text": "  No drinking water\nin our village. ",
            },
        )
        self.assertEqual(complaint_response.status_code, 201, complaint_response.text)
        complaint = complaint_response.json()
        self.assertEqual(complaint["district"], "Ranchi")
        self.assertEqual(complaint["place"], "Morabadi")
        self.assertEqual(complaint["report_text"], "No drinking water in our village.")

        listing = self.client.get("/api/v1/complaints", auth=auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["report_id"] for item in listing.json()], [complaint["report_id"]])

        feedback_response = self.client.post(
            f"/api/v1/complaints/{complaint['report_id']}/feedback",
            auth=auth,
            json={"status": "Partially solved", "feedback_text": "  Work   started. "},
        )
        self.assertEqual(feedback_response.status_code, 201, feedback_response.text)
        self.assertEqual(feedback_response.json()["feedback_text"], "Work started.")
        history = self.client.get(
            f"/api/v1/complaints/{complaint['report_id']}/feedback",
            auth=auth,
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 1)

    def test_complaint_can_be_submitted_without_a_place(self):
        citizen = self.register("reporter_without_place")
        response = self.client.post(
            "/api/v1/complaints",
            auth=(citizen["email"], citizen["password"]),
            json={
                "district": "Ranchi",
                "report_text": (
                    "Polluted water is making people in our community sick."
                ),
                "severity": "high",
                "affected_population": 15,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["place"], "")

    def test_authentication_and_owner_scope(self):
        owner_auth = self.register("owner_user")
        other_auth = self.register("other_user")
        created = self.client.post(
            "/api/v1/complaints",
            auth=(owner_auth["email"], owner_auth["password"]),
            json={
                "district": "Bokaro",
                "place": "Sector 4",
                "report_text": "Street lights are not working.",
            },
        )
        report_id = created.json()["report_id"]

        self.assertEqual(self.client.get("/api/v1/complaints").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/complaints",
                auth=(owner_auth["email"], "incorrect-password"),
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/complaints/{report_id}",
                auth=(other_auth["email"], other_auth["password"]),
            ).status_code,
            404,
        )
        other_listing = self.client.get(
            "/api/v1/complaints",
            auth=(other_auth["email"], other_auth["password"]),
        )
        self.assertEqual(other_listing.json(), [])

    def test_invalid_input_and_duplicate_username_are_rejected(self):
        self.register("unique_user")
        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "unique_user",
                "email": "new-unique-user@example.com",
                "password": "a-secure-test-password",
                "password_confirmation": "a-secure-test-password",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        auth = ("unique_user@example.com", "a-secure-test-password")
        invalid_district = self.client.post(
            "/api/v1/complaints",
            auth=auth,
            json={
                "district": "Not a district",
                "place": "Village",
                "report_text": "Issue description",
            },
        )
        self.assertEqual(invalid_district.status_code, 422)


if __name__ == "__main__":
    unittest.main()
