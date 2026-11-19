import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.store import connection, utc_now
from authentication import LEGACY_PASSWORD_ITERATIONS

ADMIN_USER = "root_admin"
ADMIN_PASSWORD = "admin-test-password-123"
PASSWORD = "citizen-test-password-1"


class Phase5ApiTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="challengemap-phase5-")
        database_path = Path(self.temp_dir.name) / "api.db"
        self.env = patch.dict(
            os.environ,
            {
                "CHALLENGEMAP_DB_PATH": str(database_path),
                "JWT_SECRET": "unit-test-secret",
                "CHALLENGEMAP_BOOTSTRAP_ADMIN": f"{ADMIN_USER}:{ADMIN_PASSWORD}",
                "CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL": "root-admin@example.com",
                "DEDUP_THRESHOLD": "0.86",
                "ENV": "test",
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
    def login(self, identifier: str, password: str) -> dict:
        with connection() as conn:
            account = conn.execute(
                "SELECT email, role FROM users "
                "WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
                (identifier, identifier),
            ).fetchone()
        self.assertIsNotNone(account, f"No test account for {identifier}")
        self.assertTrue(account["email"], f"Test account {identifier} needs an email")
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": account["email"],
                "password": password,
                "role": account["role"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    @staticmethod
    def bearer(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def admin(self) -> dict[str, str]:
        return self.bearer(self.login(ADMIN_USER, ADMIN_PASSWORD)["access_token"])

    def citizen(self, username: str = "citizen_one") -> tuple[dict, dict[str, str]]:
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
        tokens = self.login(username, PASSWORD)
        return response.json(), self.bearer(tokens["access_token"])

    def submit(self, headers, text: str, district: str = "Ranchi", **extra) -> dict:
        response = self.client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "district": district,
                "place": "Ward 4",
                "report_text": text,
                **extra,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def seed_complaints(self, headers, count: int = 8) -> list[dict]:
        texts = [
            "handpump is dry near the school",
            "pipe water supply has stopped",
            "no water from the public tap",
            "school has no teacher for science",
            "road culvert damaged after rain",
            "street light not working at night",
            "ration dealer gives short weight",
            "pension not received for months",
        ]
        return [
            self.submit(headers, f"{texts[index % len(texts)]} report {index}")
            for index in range(count)
        ]

    # --- authentication ----------------------------------------------------
    def test_legacy_pbkdf2_account_logs_in_and_is_upgraded_to_argon2id(self):
        """A row written before the Argon2id upgrade keeps working, then migrates."""
        salt = b"0123456789abcdef"
        legacy_hash = hashlib.pbkdf2_hmac(
            "sha256", PASSWORD.encode(), salt, LEGACY_PASSWORD_ITERATIONS
        ).hex()
        now = utc_now()
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    username, password_salt, password_hash, full_name, email,
                    role, district, created_at, updated_at
                ) VALUES (?, ?, ?, '', ?, 'citizen', 'Ranchi', ?, ?)
                """,
                ("legacy_user", salt.hex(), legacy_hash, "legacy@example.com", now, now),
            )

        self.login("legacy_user", PASSWORD)

        with connection() as conn:
            row = conn.execute(
                "SELECT password_salt, password_hash FROM users "
                "WHERE username = 'legacy_user'"
            ).fetchone()
        self.assertEqual(row["password_salt"], "argon2id")
        self.assertTrue(row["password_hash"].startswith("$argon2id$"))

    def test_health_reports_database_ok(self):
        payload = self.client.get("/api/v1/health").json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "ok")

    def test_login_issues_tokens_and_profile_requires_one(self):
        self.citizen()
        tokens = self.login("citizen_one", PASSWORD)
        headers = self.bearer(tokens["access_token"])
        profile = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["username"], "citizen_one")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me", headers=self.bearer("not-a-valid-token")
            ).status_code,
            401,
        )

    def test_partner_signup_waits_for_admin_approval(self):
        response = self.client.post(
            "/api/v1/auth/register/partner",
            json={
                "username": "partner_applicant",
                "email": "partner-applicant@example.com",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
                "full_name": "Partner Applicant",
                "district": "Ranchi",
                "organization_name": "Community Research Group",
                "job_title": "Programme Lead",
            },
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertIn("approval", response.json()["message"].lower())

        rejected_login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "partner-applicant@example.com",
                "password": PASSWORD,
                "role": "partner",
            },
        )
        self.assertEqual(rejected_login.status_code, 401)
        self.assertNotIn(
            "Community Research Group",
            {organization["name"] for organization in self.client.get("/api/v1/partners").json()},
        )

        admin = self.admin()
        listing = self.client.get("/api/v1/admin/users", headers=admin)
        self.assertEqual(listing.status_code, 200, listing.text)
        applicant = next(
            row for row in listing.json() if row["username"] == "partner_applicant"
        )
        self.assertTrue(applicant["approval_pending"])
        self.assertFalse(applicant["is_active"])
        self.assertEqual(applicant["organization_name"], "Community Research Group")
        self.assertEqual(applicant["job_title"], "Programme Lead")

        approved = self.client.patch(
            f"/api/v1/admin/users/{applicant['id']}",
            headers=admin,
            json={"is_active": True},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertTrue(approved.json()["is_active"])
        self.assertFalse(approved.json()["approval_pending"])
        self.assertIsNotNone(approved.json()["organization_id"])

        partner = self.bearer(
            self.login("partner_applicant", PASSWORD)["access_token"]
        )
        self.assertEqual(
            self.client.get("/api/v1/partners/me/matches", headers=partner).status_code,
            200,
        )
        self.assertIn(
            "Community Research Group",
            {organization["name"] for organization in self.client.get("/api/v1/partners").json()},
        )

    def test_refresh_rotates_and_rejects_replay(self):
        self.citizen()
        tokens = self.login("citizen_one", PASSWORD)
        rotated = self.client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        fresh = self.bearer(rotated.json()["access_token"])
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=fresh).status_code, 200)
        replay = self.client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        self.assertEqual(replay.status_code, 401)

    # --- RBAC --------------------------------------------------------------
    def test_missing_token_is_401_and_wrong_role_is_403(self):
        self.citizen()
        headers = self.bearer(self.login("citizen_one", PASSWORD)["access_token"])
        self.assertEqual(self.client.get("/api/v1/admin/stats").status_code, 401)
        self.assertEqual(
            self.client.get("/api/v1/admin/stats", headers=headers).status_code, 403
        )
        forbidden_create = self.client.post(
            "/api/v1/admin/users",
            headers=headers,
            json={
                "username": "sneaky_partner",
                "password": PASSWORD,
                "role": "partner",
                "email": "sneaky@example.com",
            },
        )
        self.assertEqual(forbidden_create.status_code, 403)

    # --- staff and partners ------------------------------------------------
    def test_admin_creates_partner_linked_to_organization(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "partner_one",
                "password": PASSWORD,
                "role": "partner",
                "email": "partner-one@example.com",
                "organization_id": 1,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["role"], "partner")
        partner = self.bearer(self.login("partner_one", PASSWORD)["access_token"])
        matches = self.client.get("/api/v1/partners/me/matches", headers=partner)
        self.assertEqual(matches.status_code, 200)
        self.assertEqual(matches.json(), [])

    def test_partner_without_organization_gets_conflict(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "partner_two",
                "password": PASSWORD,
                "role": "partner",
                "email": "partner-two@example.com",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        partner = self.bearer(self.login("partner_two", PASSWORD)["access_token"])
        response = self.client.get("/api/v1/partners/me/matches", headers=partner)
        self.assertEqual(response.status_code, 409)

    def test_admin_lists_and_updates_accounts(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "listed_citizen",
                "password": PASSWORD,
                "role": "citizen",
                "email": "listed-citizen@example.com",
                "district": "Bokaro",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["role"], "citizen")
        self.assertTrue(created.json()["is_active"])
        self.assertNotIn("password_hash", created.json())

        listing = self.client.get("/api/v1/admin/users", headers=admin)
        self.assertEqual(listing.status_code, 200, listing.text)
        by_name = {row["username"]: row for row in listing.json()}
        self.assertIn(ADMIN_USER, by_name)
        self.assertIn("listed_citizen", by_name)

        promoted = self.client.patch(
            f"/api/v1/admin/users/{by_name['listed_citizen']['id']}",
            headers=admin,
            json={"role": "partner", "organization_id": 1},
        )
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertEqual(promoted.json()["role"], "partner")
        self.assertEqual(promoted.json()["organization_id"], 1)

        cleared_email = self.client.patch(
            f"/api/v1/admin/users/{by_name['listed_citizen']['id']}",
            headers=admin,
            json={"email": None},
        )
        self.assertEqual(cleared_email.status_code, 422, cleared_email.text)

        deactivated = self.client.patch(
            f"/api/v1/admin/users/{by_name['listed_citizen']['id']}",
            headers=admin,
            json={"is_active": False},
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertFalse(deactivated.json()["is_active"])
        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "listed-citizen@example.com",
                "password": PASSWORD,
                "role": "citizen",
            },
        )
        self.assertEqual(login.status_code, 401)

    def test_admin_cannot_demote_or_deactivate_self(self):
        admin = self.admin()
        me = self.client.get("/api/v1/auth/me", headers=admin).json()
        demote = self.client.patch(
            f"/api/v1/admin/users/{me['id']}", headers=admin, json={"role": "citizen"}
        )
        self.assertEqual(demote.status_code, 409)
        deactivate = self.client.patch(
            f"/api/v1/admin/users/{me['id']}", headers=admin, json={"is_active": False}
        )
        self.assertEqual(deactivate.status_code, 409)

    def test_user_management_requires_admin(self):
        _, headers = self.citizen()
        self.assertEqual(
            self.client.get("/api/v1/admin/users", headers=headers).status_code, 403
        )
        self.assertEqual(self.client.get("/api/v1/admin/users").status_code, 401)
        update = self.client.patch(
            "/api/v1/admin/users/1", headers=headers, json={"role": "admin"}
        )
        self.assertEqual(update.status_code, 403)

    def test_unknown_organization_is_rejected(self):
        admin = self.admin()
        response = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "partner_three",
                "password": PASSWORD,
                "role": "partner",
                "email": "partner-three@example.com",
                "organization_id": 999,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_admin_created_accounts_require_email(self):
        response = self.client.post(
            "/api/v1/admin/users",
            headers=self.admin(),
            json={
                "username": "no_staff_email",
                "password": PASSWORD,
                "role": "partner",
                "organization_id": 1,
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    # --- complaints and duplicates ----------------------------------------
    def test_complaint_submission_is_citizen_only(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "submitting_partner",
                "password": PASSWORD,
                "role": "partner",
                "email": "submitting-partner@example.com",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        partner = self.bearer(
            self.login("submitting_partner", PASSWORD)["access_token"]
        )
        payload = {
            "district": "Ranchi",
            "report_text": "handpump is dry near the school",
        }
        self.assertEqual(
            self.client.post("/api/v1/complaints", headers=partner, json=payload).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/v1/complaints", headers=admin, json=payload).status_code,
            403,
        )

    def test_submission_starts_pending_without_candidates(self):
        _, headers = self.citizen()
        complaint = self.submit(headers, "handpump is dry near the school")
        self.assertEqual(complaint["status"], "pending")
        self.assertEqual(complaint["duplicate_candidates"], [])
        self.assertEqual(complaint["is_synthetic"], 0)

    def test_duplicate_submission_suggests_candidate(self):
        _, headers = self.citizen()
        first = self.submit(headers, "handpump is dry near the school")
        second = self.submit(headers, "handpump is dry near the school")
        self.assertEqual(len(second["duplicate_candidates"]), 1)
        candidate = second["duplicate_candidates"][0]
        self.assertEqual(candidate["report_id"], first["report_id"])
        self.assertGreaterEqual(candidate["similarity"], 0.86)

    def test_duplicates_are_not_compared_across_districts(self):
        _, headers = self.citizen()
        self.submit(headers, "handpump is dry near the school", district="Ranchi")
        other = self.submit(
            headers, "handpump is dry near the school", district="Bokaro"
        )
        self.assertEqual(other["duplicate_candidates"], [])

    def test_merge_links_reports_and_conflicts_on_repeat(self):
        _, headers = self.citizen()
        first = self.submit(headers, "street light not working at night")
        second = self.submit(headers, "street light not working at night")
        merged = self.client.post(
            f"/api/v1/complaints/{second['report_id']}/merge",
            headers=headers,
            json={"keep_report_id": first["report_id"]},
        )
        self.assertEqual(merged.status_code, 200, merged.text)
        self.assertEqual(merged.json()["status"], "merged")
        self.assertEqual(merged.json()["duplicate_of"], first["report_id"])
        again = self.client.post(
            f"/api/v1/complaints/{second['report_id']}/merge",
            headers=headers,
            json={"keep_report_id": first["report_id"]},
        )
        self.assertEqual(again.status_code, 409)

    def test_merge_attaches_to_another_citizens_report_in_same_district(self):
        """Cross-account attachment is the duplicate interception the UI offers."""
        _, first_headers = self.citizen("owner_a")
        _, other_headers = self.citizen("owner_b")
        theirs = self.submit(first_headers, "ration dealer gives short weight")
        mine = self.submit(other_headers, "ration dealer gives short weight")
        response = self.client.post(
            f"/api/v1/complaints/{mine['report_id']}/merge",
            headers=other_headers,
            json={"keep_report_id": theirs["report_id"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "merged")
        self.assertEqual(response.json()["duplicate_of"], theirs["report_id"])

        # Attaching must never modify the report being attached to. Its status
        # may have moved on to "clustered" because submissions cluster in the
        # background, but it must never become merged or point at another row.
        target = self.client.get(
            f"/api/v1/complaints/{theirs['report_id']}", headers=first_headers
        )
        self.assertEqual(target.status_code, 200)
        self.assertIn(target.json()["status"], {"pending", "clustered"})
        self.assertIsNone(target.json()["duplicate_of"])

    def test_merge_still_requires_ownership_of_the_report_being_merged(self):
        _, first_headers = self.citizen("owner_a")
        _, other_headers = self.citizen("owner_b")
        theirs = self.submit(first_headers, "handpump is dry near the school")
        mine = self.submit(other_headers, "handpump is dry near the school")
        response = self.client.post(
            f"/api/v1/complaints/{theirs['report_id']}/merge",
            headers=other_headers,
            json={"keep_report_id": mine["report_id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_merge_rejects_a_target_in_another_district(self):
        _, headers = self.citizen()
        mine = self.submit(headers, "handpump is dry near the school", district="Ranchi")
        far = self.submit(headers, "handpump is dry near the school", district="Bokaro")
        response = self.client.post(
            f"/api/v1/complaints/{mine['report_id']}/merge",
            headers=headers,
            json={"keep_report_id": far["report_id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_merge_rejects_a_target_that_is_already_merged(self):
        _, headers = self.citizen()
        first = self.submit(headers, "street light not working at night")
        second = self.submit(headers, "street light not working at night")
        third = self.submit(headers, "street light not working at night")
        self.client.post(
            f"/api/v1/complaints/{second['report_id']}/merge",
            headers=headers,
            json={"keep_report_id": first["report_id"]},
        )
        chained = self.client.post(
            f"/api/v1/complaints/{third['report_id']}/merge",
            headers=headers,
            json={"keep_report_id": second["report_id"]},
        )
        self.assertEqual(chained.status_code, 409)

    def test_admin_queue_filters_by_status(self):
        _, headers = self.citizen()
        self.submit(headers, "pension not received for months")
        admin = self.admin()
        pending = self.client.get(
            "/api/v1/admin/complaints?status=pending", headers=admin
        )
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(len(pending.json()), 1)
        merged = self.client.get("/api/v1/admin/complaints?status=merged", headers=admin)
        self.assertEqual(merged.json(), [])

    def test_staff_can_update_client_issues_in_organization_districts(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "issue_staff",
                "password": PASSWORD,
                "role": "partner",
                "email": "issue-staff@example.com",
                "organization_id": 1,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        staff = self.bearer(self.login("issue_staff", PASSWORD)["access_token"])
        citizen, citizen_headers = self.citizen("issue_reporter")
        in_area = self.submit(
            citizen_headers, "No drinking water at the public tap", district="Ranchi"
        )
        outside_area = self.submit(
            citizen_headers, "No drinking water at the public tap", district="Bokaro"
        )

        queue = self.client.get("/api/v1/staff/issues", headers=staff)
        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertEqual(
            [issue["report_id"] for issue in queue.json()], [in_area["report_id"]]
        )

        update = self.client.post(
            f"/api/v1/staff/issues/{in_area['report_id']}/responses",
            headers=staff,
            json={
                "status": "in_progress",
                "response_text": "  A field team   has been assigned. ",
            },
        )
        self.assertEqual(update.status_code, 201, update.text)
        self.assertEqual(update.json()["response_text"], "A field team has been assigned.")

        citizen_reports = self.client.get(
            "/api/v1/complaints", headers=citizen_headers
        ).json()
        updated_report = next(
            report
            for report in citizen_reports
            if report["report_id"] == in_area["report_id"]
        )
        self.assertEqual(updated_report["staff_response_status"], "in_progress")
        self.assertEqual(
            updated_report["staff_response_text"],
            "A field team has been assigned.",
        )
        admin_reports = self.client.get(
            "/api/v1/admin/complaints", headers=admin
        ).json()
        admin_report = next(
            report
            for report in admin_reports
            if report["report_id"] == in_area["report_id"]
        )
        self.assertEqual(
            admin_report["staff_response_status"], "in_progress"
        )
        self.assertEqual(
            admin_report["staff_response_text"],
            "A field team has been assigned.",
        )
        self.assertEqual(admin_report["staff_responded_at"], update.json()["created_at"])

        outside_update = self.client.post(
            f"/api/v1/staff/issues/{outside_area['report_id']}/responses",
            headers=staff,
            json={"status": "acknowledged", "response_text": "We received this report."},
        )
        self.assertEqual(outside_update.status_code, 404)
        self.assertEqual(
            self.client.get("/api/v1/staff/issues", headers=citizen_headers).status_code,
            403,
        )

    def test_staff_response_requires_nonblank_client_message(self):
        admin = self.admin()
        self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "blank_response_staff",
                "password": PASSWORD,
                "role": "partner",
                "email": "blank-response-staff@example.com",
                "organization_id": 1,
            },
        )
        staff = self.bearer(
            self.login("blank_response_staff", PASSWORD)["access_token"]
        )
        _, citizen_headers = self.citizen("blank_response_reporter")
        report = self.submit(citizen_headers, "Water pipe has been broken for days")
        response = self.client.post(
            f"/api/v1/staff/issues/{report['report_id']}/responses",
            headers=staff,
            json={"status": "acknowledged", "response_text": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_admin_can_use_staff_issue_queue_across_districts(self):
        admin = self.admin()
        _, citizen_headers = self.citizen("admin_issue_reporter")
        ranchi = self.submit(
            citizen_headers, "Public water tap is broken", district="Ranchi"
        )
        bokaro = self.submit(
            citizen_headers, "Road is blocked near the market", district="Bokaro"
        )

        queue = self.client.get("/api/v1/staff/issues", headers=admin)
        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertEqual(
            {issue["report_id"] for issue in queue.json()},
            {ranchi["report_id"], bokaro["report_id"]},
        )

        response = self.client.post(
            f"/api/v1/staff/issues/{bokaro['report_id']}/responses",
            headers=admin,
            json={
                "status": "acknowledged",
                "response_text": "The department has received your report.",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

    # --- challenge generation and lifecycle --------------------------------
    def test_recluster_requires_a_queue(self):
        admin = self.admin()
        response = self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        self.assertEqual(response.status_code, 409)

    def test_recluster_requires_at_least_two_reports(self):
        _, headers = self.citizen()
        self.submit(headers, "Water supply stopped near the primary school")
        response = self.client.post(
            "/api/v1/admin/jobs/recluster",
            headers=self.admin(),
            json={"clusters": 2},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("at least 2", response.json()["detail"])

    def test_recluster_accepts_two_complaints(self):
        _, headers = self.citizen()
        self.submit(headers, "Water supply stopped near the primary school")
        self.submit(headers, "Street light is broken beside the market")
        response = self.client.post(
            "/api/v1/admin/jobs/recluster",
            headers=self.admin(),
            json={"clusters": 2},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["complaints_clustered"], 2)

    def test_recluster_creates_drafts_and_matches(self):
        _, headers = self.citizen()
        self.seed_complaints(headers)
        admin = self.admin()
        result = self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        self.assertEqual(result.status_code, 200, result.text)
        payload = result.json()
        self.assertEqual(payload["challenges_created"], 2)
        self.assertEqual(payload["complaints_clustered"], 8)
        self.assertGreater(payload["matches_created"], 0)
        drafts = self.client.get("/api/v1/challenges?status=draft", headers=admin)
        self.assertEqual(len(drafts.json()), 2)
        self.assertEqual(self.client.get("/api/v1/challenges").json(), [])

    def test_publish_makes_challenge_public(self):
        _, headers = self.citizen()
        self.seed_complaints(headers)
        admin = self.admin()
        self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        drafts = self.client.get("/api/v1/challenges?status=draft", headers=admin).json()
        published = self.client.post(
            f"/api/v1/challenges/{drafts[0]['id']}/publish", headers=admin
        )
        self.assertEqual(published.status_code, 200, published.text)
        public = self.client.get("/api/v1/challenges").json()
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["slug"], published.json()["slug"])

    def test_challenge_detail_includes_evidence_districts_and_timeline(self):
        _, headers = self.citizen()
        self.seed_complaints(headers)
        admin = self.admin()
        self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        drafts = self.client.get(
            "/api/v1/challenges?status=draft", headers=admin
        ).json()
        published = self.client.post(
            f"/api/v1/challenges/{drafts[0]['id']}/publish", headers=admin
        ).json()

        detail = self.client.get(f"/api/v1/challenges/{published['slug']}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertTrue(body["evidence"])
        self.assertEqual(len(body["evidence"]), body["complaint_count"])
        self.assertEqual(body["district_count"], 1)
        self.assertEqual(body["district_names"], ["Ranchi"])
        self.assertEqual(body["districts"], [{"district": "Ranchi", "complaints": body["complaint_count"]}])
        self.assertTrue(body["timeline"])
        self.assertEqual(
            sum(point["complaints"] for point in body["timeline"]),
            body["complaint_count"],
        )
        self.assertIn(body["severity"], {"low", "medium", "high", "critical"})
        self.assertIsNotNone(body["first_reported_at"])
        self.assertIsNotNone(body["last_reported_at"])

        matches = self.client.get(
            f"/api/v1/challenges/{published['slug']}/matches"
        ).json()
        self.assertTrue(matches)
        self.assertTrue(matches[0]["organization_type"])
        self.assertIsInstance(matches[0]["organization_districts"], list)

    def test_challenge_editing_requires_admin(self):
        _, headers = self.citizen()
        self.seed_complaints(headers)
        admin = self.admin()
        self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        drafts = self.client.get("/api/v1/challenges?status=draft", headers=admin).json()
        forbidden = self.client.patch(
            f"/api/v1/challenges/{drafts[0]['id']}",
            headers=headers,
            json={"title": "Renamed challenge"},
        )
        self.assertEqual(forbidden.status_code, 403)
        allowed = self.client.patch(
            f"/api/v1/challenges/{drafts[0]['id']}",
            headers=admin,
            json={"title": "Renamed challenge"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["title"], "Renamed challenge")

    def test_partner_interest_then_admin_confirmation(self):
        _, headers = self.citizen()
        self.seed_complaints(headers)
        admin = self.admin()
        self.client.post(
            "/api/v1/admin/jobs/recluster", headers=admin, json={"clusters": 2}
        )
        drafts = self.client.get("/api/v1/challenges?status=draft", headers=admin).json()
        published = self.client.post(
            f"/api/v1/challenges/{drafts[0]['id']}/publish", headers=admin
        ).json()
        matches = self.client.get(f"/api/v1/challenges/{published['slug']}/matches")
        self.assertEqual(matches.status_code, 200)
        self.assertTrue(matches.json())
        match = matches.json()[0]

        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "partner_four",
                "password": PASSWORD,
                "role": "partner",
                "email": "partner-four@example.com",
                "organization_id": match["organization_id"],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        partner = self.bearer(self.login("partner_four", PASSWORD)["access_token"])

        mine = self.client.get("/api/v1/partners/me/matches", headers=partner)
        self.assertIn(match["id"], [item["id"] for item in mine.json()])
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

    # --- analytics and misc ------------------------------------------------
    def test_analytics_districts_covers_all_24(self):
        _, headers = self.citizen()
        self.submit(headers, "handpump is dry near the school", district="Ranchi")
        self.submit(headers, "pipe water supply has stopped", district="Bokaro")
        stats = self.client.get("/api/v1/analytics/districts").json()
        self.assertEqual(len(stats), 24)
        by_name = {row["district"]: row["complaints"] for row in stats}
        self.assertEqual(by_name["Ranchi"], 1)
        self.assertEqual(by_name["Bokaro"], 1)
        self.assertEqual(by_name["Chatra"], 0)

    def test_analytics_trends_group_by_month(self):
        _, headers = self.citizen()
        self.submit(headers, "handpump is dry near the school")
        trends = self.client.get("/api/v1/analytics/trends").json()
        self.assertTrue(trends)
        self.assertEqual(len(trends[0]["month"]), 7)
        self.assertEqual(trends[0]["domain"], "unassigned")

    def test_admin_stats_counts_the_queue(self):
        _, headers = self.citizen()
        self.submit(headers, "handpump is dry near the school")
        response = self.client.get("/api/v1/admin/stats", headers=self.admin())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["complaints"], 1)
        self.assertEqual(body["pending"], 1)
        self.assertEqual(body["users"], 2)

    def test_unknown_challenge_and_match_are_not_found(self):
        self.assertEqual(
            self.client.get("/api/v1/challenges/does-not-exist").status_code, 404
        )
        admin = self.admin()
        self.assertEqual(
            self.client.patch(
                "/api/v1/admin/matches/999", headers=admin, json={"action": "confirm"}
            ).status_code,
            404,
        )

    def test_model_metrics_are_admin_only(self):
        self.assertEqual(self.client.get("/api/v1/models").status_code, 401)
        _, headers = self.citizen()
        self.assertEqual(
            self.client.get("/api/v1/models", headers=headers).status_code, 403
        )
        response = self.client.get("/api/v1/models", headers=self.admin())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("clustering", response.json())

    def test_request_id_header_is_returned(self):
        response = self.client.get(
            "/api/v1/health", headers={"x-request-id": "abc-123"}
        )
        self.assertEqual(response.headers["x-request-id"], "abc-123")

    def test_account_email_works_as_a_login_name(self):
        admin = self.admin()
        created = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "staff_mail",
                "password": PASSWORD,
                "role": "partner",
                "email": "Staff.Mail@Example.com",
                "organization_id": 1,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["email"], "Staff.Mail@Example.com")

        # Email is case-insensitive, and username-based JWT login is rejected.
        by_email = self.login("staff.mail@example.com", PASSWORD)
        self.assertEqual(by_email["user"]["id"], created.json()["id"])
        self.assertEqual(
            self.login("staff_mail", PASSWORD)["user"]["id"], created.json()["id"]
        )
        username_login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "staff_mail", "password": PASSWORD, "role": "partner"},
        )
        self.assertEqual(username_login.status_code, 422, username_login.text)

        # A duplicate address is refused rather than silently shared.
        duplicate = self.client.post(
            "/api/v1/admin/users",
            headers=admin,
            json={
                "username": "staff_mail_two",
                "password": PASSWORD,
                "role": "partner",
                "email": "staff.mail@example.com",
                "organization_id": 1,
            },
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_citizen_registration_email_only_login(self):
        created = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "email_citizen",
                "email": " Citizen.Mail@Example.com ",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
                "district": "Ranchi",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["email"], "Citizen.Mail@Example.com")

        by_email = self.login("citizen.mail@example.com", PASSWORD)
        by_username = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "email_citizen",
                "password": PASSWORD,
                "role": "citizen",
            },
        )
        self.assertEqual(by_email["user"]["id"], created.json()["id"])
        self.assertEqual(by_username.status_code, 422, by_username.text)

        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "another_citizen",
                "email": "citizen.mail@example.com",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_citizen_registration_rejects_invalid_email(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "invalid_email",
                "email": "not-an-email",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_bootstrap_admin_email_is_applied_and_loginable(self):
        os.environ["CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL"] = "root@example.com"
        # Restart the client so the lifespan startup hook runs again.
        self.client.__exit__(None, None, None)
        self.client = TestClient(app)
        self.client.__enter__()

        tokens = self.login("root@example.com", ADMIN_PASSWORD)
        self.assertEqual(tokens["user"]["role"], "admin")
        self.assertEqual(tokens["user"]["email"], "root@example.com")
        username_login = self.client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_USER, "password": ADMIN_PASSWORD, "role": "admin"},
        )
        self.assertEqual(username_login.status_code, 422, username_login.text)

    def test_selected_role_must_match_email_account_role(self):
        created, _ = self.citizen("role_check")
        correct_role = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": created["email"],
                "password": PASSWORD,
                "role": "citizen",
            },
        )
        self.assertEqual(correct_role.status_code, 200, correct_role.text)

        for role in ("partner", "admin"):
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": created["email"],
                    "password": PASSWORD,
                    "role": role,
                },
            )
            self.assertEqual(response.status_code, 401, response.text)

    def test_register_requires_email(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "missing_email",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()
