import unittest

import numpy as np

from src.nlp.topic_discovery import (
    cluster_sentence_embeddings,
    discover_sentence_topics,
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


class TopicDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.texts = [
            "पानी की कमी",
            "जल आपूर्ति बंद",
            "road is broken",
            "damaged road",
            "school needs teachers",
            "teacher shortage at school",
        ]
        self.embeddings = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.98, 0.02, 0.0],
                [0.0, 1.0, 0.0],
                [0.02, 0.98, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 0.02, 0.98],
            ],
            dtype=np.float32,
        )

    def test_discovers_groups_and_returns_measured_metrics(self):
        assignments, summary, metrics = cluster_sentence_embeddings(
            self.texts,
            self.embeddings,
            n_clusters=3,
        )
        self.assertEqual(len(assignments), len(self.texts))
        self.assertEqual(len(summary), 3)
        self.assertEqual(int(summary["complaints"].sum()), len(self.texts))
        self.assertTrue(assignments["cluster_similarity"].between(0, 1).all())
        self.assertGreater(metrics["silhouette_cosine"], 0.9)
        self.assertIsNotNone(metrics["davies_bouldin"])
        for topic_id in summary["topic_id"]:
            group_texts = assignments.loc[
                assignments["topic_id"] == topic_id, "complaint_text"
            ].tolist()
            self.assertTrue(
                all(text in group_texts for text in (
                    summary.loc[
                        summary["topic_id"] == topic_id,
                        "representative_complaints",
                    ].iloc[0].split(" | ")
                ))
            )

    def test_encoder_pipeline_returns_row_aligned_assignments(self):
        encoder = FakeEncoder(self.embeddings)
        assignments, _, _ = discover_sentence_topics(
            self.texts,
            encoder,
            n_clusters=3,
        )
        self.assertEqual(assignments["complaint_text"].tolist(), self.texts)

    def test_rejects_bad_inputs_that_cannot_produce_requested_groups(self):
        with self.assertRaisesRegex(ValueError, "At least three"):
            cluster_sentence_embeddings(self.texts[:2], self.embeddings[:2], 2)
        with self.assertRaisesRegex(ValueError, "n_clusters must be"):
            cluster_sentence_embeddings(self.texts, self.embeddings, len(self.texts))
        with self.assertRaisesRegex(ValueError, "zero-length"):
            cluster_sentence_embeddings(
                self.texts,
                np.zeros_like(self.embeddings),
                n_clusters=2,
            )
        identical = np.ones((4, 2), dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "only 1 distinct vectors"):
            cluster_sentence_embeddings(["a", "b", "c", "d"], identical, 3)


if __name__ == "__main__":
    unittest.main()
