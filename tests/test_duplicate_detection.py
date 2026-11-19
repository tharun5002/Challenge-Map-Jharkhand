import unittest

import numpy as np

from src.nlp.duplicate_detection import (
    detect_duplicate_candidates,
    find_duplicate_candidates,
)


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors

    def encode(
        self,
        sentences,
        *,
        batch_size,
        show_progress_bar,
        convert_to_numpy,
        normalize_embeddings,
    ):
        return self.vectors


class DuplicateDetectionTests(unittest.TestCase):
    def setUp(self):
        self.ids = ["c-1", "c-2", "c-3", "c-4"]
        self.texts = [
            "पानी की आपूर्ति बंद है",
            "पानी की सप्लाई बंद है",
            "A road has a pothole",
            "The school needs teachers",
        ]
        self.embeddings = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.98, 0.02, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

    def test_returns_unique_sorted_pairs_with_pending_review_evidence(self):
        candidates = find_duplicate_candidates(
            self.ids,
            self.texts,
            self.embeddings,
            similarity_threshold=0.95,
        )
        self.assertEqual(len(candidates), 1)
        pair = candidates.iloc[0]
        self.assertEqual(pair["complaint_id"], "c-1")
        self.assertEqual(pair["similar_complaint_id"], "c-2")
        self.assertGreaterEqual(pair["similarity"], 0.95)
        self.assertEqual(pair["review_status"], "pending_review")
        self.assertIn("पानी", pair["complaint_text"])

    def test_respects_threshold_and_returns_empty_schema_when_no_match(self):
        no_matches = find_duplicate_candidates(
            self.ids,
            self.texts,
            self.embeddings,
            similarity_threshold=1.0,
        )
        self.assertTrue(no_matches.empty)
        self.assertEqual(
            list(no_matches.columns),
            [
                "complaint_id",
                "similar_complaint_id",
                "similarity",
                "complaint_text",
                "similar_complaint_text",
                "review_status",
            ],
        )

    def test_encoder_entry_point_preserves_row_alignment(self):
        candidates = detect_duplicate_candidates(
            self.ids,
            self.texts,
            FakeEncoder(self.embeddings),
            similarity_threshold=0.95,
        )
        self.assertEqual(candidates.iloc[0]["complaint_id"], "c-1")
        self.assertEqual(candidates.iloc[0]["similar_complaint_id"], "c-2")

    def test_rejects_malformed_inputs(self):
        with self.assertRaisesRegex(ValueError, "At least two"):
            find_duplicate_candidates(["c-1"], ["one"], self.embeddings[:1])
        with self.assertRaisesRegex(ValueError, "same length"):
            find_duplicate_candidates(self.ids, self.texts[:2], self.embeddings)
        with self.assertRaisesRegex(ValueError, "unique"):
            find_duplicate_candidates(
                ["c-1", "c-1", "c-3", "c-4"], self.texts, self.embeddings
            )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            find_duplicate_candidates(
                ["c-1", None, "c-3", "c-4"], self.texts, self.embeddings
            )
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            find_duplicate_candidates(
                self.ids, self.texts, self.embeddings, similarity_threshold=1.2
            )
        with self.assertRaisesRegex(ValueError, "non-empty vector"):
            find_duplicate_candidates(self.ids, self.texts, self.embeddings[:-1])
        with self.assertRaisesRegex(ValueError, "zero-length"):
            find_duplicate_candidates(
                self.ids, self.texts, np.zeros_like(self.embeddings)
            )


if __name__ == "__main__":
    unittest.main()
