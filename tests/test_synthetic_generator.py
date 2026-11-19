import re
import unittest

import pandas as pd

from src.data.complaints import (
    COMPLAINT_COLUMNS,
    DISTRICTS,
    SEVERITY_LEVELS,
    prepare_complaints,
)
from src.data.synthetic_generator import (
    DOMAINS,
    SUB_ISSUES,
    TRUTH_OUTPUT_COLUMNS,
    generate_corpus,
)


class SyntheticGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = 800
        cls.complaints, cls.truth = generate_corpus(cls.records, seed=7, id_prefix="TST")

    def test_output_is_deterministic_for_a_seed(self):
        again, again_truth = generate_corpus(self.records, seed=7, id_prefix="TST")
        pd.testing.assert_frame_equal(self.complaints, again)
        pd.testing.assert_frame_equal(self.truth, again_truth)

    def test_different_seeds_produce_different_text(self):
        other, _ = generate_corpus(self.records, seed=8, id_prefix="TST")
        self.assertNotEqual(
            self.complaints["complaint_text"].tolist()[:20],
            other["complaint_text"].tolist()[:20],
        )

    def test_canonical_schema_validates(self):
        self.assertEqual(list(self.complaints.columns), list(COMPLAINT_COLUMNS))
        self.assertEqual(list(self.truth.columns), TRUTH_OUTPUT_COLUMNS)
        # Re-validating must be a no-op and must never promote a synthetic row.
        revalidated = prepare_complaints(self.complaints)
        self.assertTrue(revalidated["source_type"].eq("synthetic").all())
        self.assertTrue(revalidated["verification_status"].eq("synthetic_not_verified").all())
        self.assertTrue(revalidated["severity"].isin(SEVERITY_LEVELS).all())
        self.assertTrue(revalidated["complaint_date"].notna().all())
        self.assertTrue(revalidated["affected_population"].notna().all())

    def test_all_districts_appear(self):
        self.assertEqual(set(self.complaints["district"].unique()), set(DISTRICTS))

    def test_ground_truth_covers_domains_and_sub_issues(self):
        self.assertTrue(set(self.truth["domain"]).issubset(set(DOMAINS.values())))
        # A small sample cannot be expected to hit all 71 sub-issues, but it must
        # span most of the taxonomy and every domain.
        self.assertGreaterEqual(self.truth["sub_issue"].nunique(), 55)
        self.assertLessEqual(self.truth["sub_issue"].nunique(), len(SUB_ISSUES))
        self.assertEqual(self.records, len(self.complaints))

    def test_duplicate_kinds_are_recorded(self):
        kinds = set(self.truth["duplicate_kind"].unique())
        self.assertEqual(kinds, {"", "exact", "near"})

    def test_duplicate_ids_and_links_are_consistent(self):
        ids = set(self.complaints["complaint_id"])
        self.assertEqual(len(ids), len(self.complaints))
        duplicates = self.truth[self.truth["is_duplicate"] == 1]
        self.assertGreater(len(duplicates), 0)

        for row in duplicates.itertuples():
            self.assertIn(row.duplicate_of, ids)
            self.assertNotEqual(row.duplicate_of, row.complaint_id)
            # A duplicate must share the group id of the report it copies.
            original_group = self.truth.loc[
                self.truth["complaint_id"] == row.duplicate_of, "duplicate_group_id"
            ].iloc[0]
            self.assertEqual(row.duplicate_group_id, original_group)

    def test_duplicate_rate_is_close_to_the_declared_injection(self):
        rate = self.truth["is_duplicate"].mean()
        self.assertAlmostEqual(rate, 0.10, delta=0.03)

    def test_exact_duplicates_are_identical_and_near_duplicates_are_not(self):
        texts = self.complaints.set_index("complaint_id")["complaint_text"]

        exact = self.truth[self.truth["duplicate_kind"] == "exact"]
        self.assertGreater(len(exact), 0)
        for row in exact.itertuples():
            self.assertEqual(texts[row.complaint_id], texts[row.duplicate_of])

        near = self.truth[self.truth["duplicate_kind"] == "near"]
        self.assertGreater(len(near), 0)
        for row in near.head(40).itertuples():
            self.assertNotEqual(texts[row.complaint_id], texts[row.duplicate_of])

    def test_texts_contain_no_direct_identifiers(self):
        phone = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
        email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
        for text in self.complaints["complaint_text"]:
            self.assertIsNone(phone.search(text))
            self.assertIsNone(email.search(text))

    def test_language_mix_is_multilingual(self):
        counts = self.complaints["language"].value_counts(normalize=True)
        self.assertGreaterEqual(set(counts.index), {"hi", "en", "hinglish"})
        self.assertGreater(counts.min(), 0.10)

    def test_dates_stay_inside_the_declared_window(self):
        dates = pd.to_datetime(self.complaints["complaint_date"])
        self.assertGreaterEqual(dates.min(), pd.Timestamp("2025-05-01"))
        self.assertLessEqual(dates.max(), pd.Timestamp("2026-10-31"))

    def test_eval_set_is_disjoint_from_training_ids(self):
        eval_complaints, eval_truth = generate_corpus(200, seed=8, id_prefix="EVAL")
        self.assertTrue(
            set(eval_complaints["complaint_id"]).isdisjoint(set(self.complaints["complaint_id"]))
        )
        self.assertTrue(eval_complaints["complaint_id"].str.startswith("EVAL-").all())
        self.assertEqual(len(eval_truth), 200)
        self.assertEqual(len(eval_complaints), 200)

    def test_rejects_non_positive_record_count(self):
        with self.assertRaises(ValueError):
            generate_corpus(0)


if __name__ == "__main__":
    unittest.main()
