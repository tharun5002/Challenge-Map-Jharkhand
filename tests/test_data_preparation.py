import unittest

import pandas as pd

from src.data.complaints import (
    COMPLAINT_COLUMNS,
    convert_legacy_synthetic,
    prepare_complaints,
)


class ComplaintDataPreparationTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            {
                "complaint_id": ["C001"],
                "complaint_text": ["  Water is unavailable  "],
                "district": ["ranchi"],
                "block": [None],
                "complaint_date": [None],
                "language": [None],
                "severity": [None],
                "affected_population": [None],
                "source_type": ["consent_survey"],
                "verification_status": [None],
            }
        )

    def test_normalizes_schema_without_inventing_unknown_values(self):
        prepared = prepare_complaints(self.data)
        self.assertEqual(tuple(prepared.columns), COMPLAINT_COLUMNS)
        self.assertEqual(prepared.loc[0, "complaint_text"], "Water is unavailable")
        self.assertEqual(prepared.loc[0, "district"], "Ranchi")
        self.assertEqual(prepared.loc[0, "language"], "unknown")
        self.assertEqual(prepared.loc[0, "severity"], "unknown")
        self.assertEqual(prepared.loc[0, "verification_status"], "unverified")
        self.assertTrue(pd.isna(prepared.loc[0, "complaint_date"]))
        self.assertTrue(pd.isna(prepared.loc[0, "affected_population"]))

    def test_rejects_duplicate_ids_unknown_districts_and_invalid_dates(self):
        with self.subTest("duplicate ID"):
            duplicate = pd.concat([self.data, self.data], ignore_index=True)
            with self.assertRaisesRegex(ValueError, "must be unique"):
                prepare_complaints(duplicate)

        with self.subTest("unknown district"):
            unknown_district = self.data.assign(district="Not a Jharkhand district")
            with self.assertRaisesRegex(ValueError, "Unknown Jharkhand district"):
                prepare_complaints(unknown_district)

        with self.subTest("invalid date"):
            invalid_date = self.data.assign(complaint_date="not-a-date")
            with self.assertRaisesRegex(ValueError, "ISO date"):
                prepare_complaints(invalid_date)

    def test_rejects_invalid_population_and_verified_synthetic_rows(self):
        with self.subTest("fractional affected population"):
            invalid_population = self.data.assign(affected_population=1.5)
            with self.assertRaisesRegex(ValueError, "whole number"):
                prepare_complaints(invalid_population)

        with self.subTest("synthetic cannot be verified"):
            verified_synthetic = self.data.assign(
                source_type="synthetic",
                verification_status="verified",
            )
            with self.assertRaisesRegex(ValueError, "cannot be marked verified"):
                prepare_complaints(verified_synthetic)

    def test_converts_legacy_examples_as_unverified_synthetic_records(self):
        legacy = pd.DataFrame(
            {
                "report_id": ["R001"],
                "district": ["Dumka"],
                "report_text": ["The school needs repairs."],
            }
        )
        prepared = convert_legacy_synthetic(legacy)
        self.assertEqual(prepared.loc[0, "complaint_id"], "R001")
        self.assertEqual(prepared.loc[0, "district"], "Dumka")
        self.assertEqual(prepared.loc[0, "source_type"], "synthetic")
        self.assertEqual(
            prepared.loc[0, "verification_status"], "synthetic_not_verified"
        )
        self.assertTrue(pd.isna(prepared.loc[0, "complaint_date"]))
        self.assertTrue(pd.isna(prepared.loc[0, "affected_population"]))


if __name__ == "__main__":
    unittest.main()
