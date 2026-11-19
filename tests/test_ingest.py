import unittest

import pandas as pd

from src.data.ingest import (
    CPGRAMS_COLUMN_MAP,
    PGMS_COLUMN_MAP,
    ingest_frame,
    resolve_columns,
    scrub_pii,
)


class IngestTests(unittest.TestCase):
    def test_scrubs_phone_email_and_identifiers(self):
        text = (
            "Call 9876543210 or write to ramesh.kumar@example.com. "
            "Aadhaar 1234 5678 9012, PAN ABCDE1234F."
        )
        cleaned = scrub_pii(text)
        self.assertNotIn("9876543210", cleaned)
        self.assertNotIn("ramesh.kumar@example.com", cleaned)
        self.assertNotIn("1234 5678 9012", cleaned)
        self.assertNotIn("ABCDE1234F", cleaned)
        self.assertIn("[phone]", cleaned)
        self.assertIn("[email]", cleaned)

    def test_resolves_aliases_case_insensitively(self):
        frame = pd.DataFrame(
            {
                "ID": ["G1"],
                "Description": ["No water in the ward"],
                "District Name": ["Ranchi"],
            }
        )
        resolved = resolve_columns(frame)
        self.assertIn("complaint_id", resolved.columns)
        self.assertIn("complaint_text", resolved.columns)
        self.assertIn("district", resolved.columns)

    def test_cpgrams_mapping_produces_canonical_rows(self):
        frame = pd.DataFrame(
            {
                "grievance_id": ["C-1"],
                "subject_content": ["Pension not received for 8 months, contact 9812345678"],
                "district": ["Dumka"],
                "diarydate": ["2026-03-04"],
            }
        )
        result = ingest_frame(frame, source_type="public_dataset", column_map=CPGRAMS_COLUMN_MAP)
        self.assertEqual(result.loc[0, "complaint_id"], "C-1")
        self.assertNotIn("9812345678", result.loc[0, "complaint_text"])
        self.assertEqual(result.loc[0, "district"], "Dumka")
        self.assertEqual(result.loc[0, "complaint_date"], "2026-03-04")
        self.assertEqual(result.loc[0, "source_type"], "public_dataset")
        self.assertEqual(result.loc[0, "verification_status"], "unverified")

    def test_pgms_mapping_requires_shipped_columns(self):
        frame = pd.DataFrame(
            {"complaint_no": ["P-9"], "complaint": ["Handpump dry"], "district_name": ["Khunti"]}
        )
        result = ingest_frame(frame, source_type="other", column_map=PGMS_COLUMN_MAP)
        self.assertEqual(result.loc[0, "district"], "Khunti")

    def test_rejects_unknown_source_type(self):
        frame = pd.DataFrame(
            {"complaint_id": ["X"], "complaint_text": ["t"], "district": ["Ranchi"]}
        )
        with self.assertRaisesRegex(ValueError, "Unknown source_type"):
            ingest_frame(frame, source_type="scraped")

    def test_rejects_missing_required_columns(self):
        frame = pd.DataFrame({"complaint_id": ["X"], "district": ["Ranchi"]})
        with self.assertRaisesRegex(ValueError, "missing required column"):
            ingest_frame(frame, source_type="other")

    def test_rejects_unknown_district_via_canonical_validation(self):
        frame = pd.DataFrame(
            {"complaint_id": ["X"], "complaint_text": ["t"], "district": ["Patna"]}
        )
        with self.assertRaisesRegex(ValueError, "Unknown Jharkhand district"):
            ingest_frame(frame, source_type="other")

    def test_synthetic_rows_cannot_be_verified(self):
        frame = pd.DataFrame(
            {
                "complaint_id": ["X"],
                "complaint_text": ["t"],
                "district": ["Ranchi"],
                "verification_status": ["verified"],
            }
        )
        with self.assertRaisesRegex(ValueError, "cannot be marked verified"):
            ingest_frame(frame, source_type="synthetic")


if __name__ == "__main__":
    unittest.main()
