import unittest

import numpy as np

from src.nlp.evaluation import (
    clustering_metrics,
    duplicate_pair_metrics,
    purity_score,
    run_clustering,
    true_duplicate_pairs,
)
from src.nlp.vectorizers import TfidfEncoder, build_encoder


class PurityTests(unittest.TestCase):
    def test_perfect_and_worst_case(self):
        self.assertAlmostEqual(purity_score([0, 0, 1, 1], [0, 0, 1, 1]), 1.0)
        # One cluster holding two of each class: its majority is 2 of 4.
        self.assertAlmostEqual(purity_score([0, 0, 1, 1], [0, 0, 0, 0]), 0.5)
        self.assertAlmostEqual(purity_score([0, 0, 1, 1], [1, 0, 1, 0]), 0.5)

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            purity_score([], [])


class ClusteringMetricTests(unittest.TestCase):
    def test_identical_labels_score_one(self):
        labels = ["water", "water", "health", "health", "roads", "roads"]
        metrics = clustering_metrics(labels, labels)
        self.assertAlmostEqual(metrics["ari"], 1.0)
        self.assertAlmostEqual(metrics["nmi"], 1.0)
        self.assertAlmostEqual(metrics["purity"], 1.0)
        self.assertEqual(metrics["n_clusters"], 3)

    def test_permuted_labels_still_score_one(self):
        truth = [0, 0, 1, 1, 2, 2]
        metrics = clustering_metrics(truth, [2, 2, 0, 0, 1, 1])
        self.assertAlmostEqual(metrics["ari"], 1.0)

    def test_single_cluster_carries_no_information(self):
        metrics = clustering_metrics([0, 0, 1, 1], [0, 0, 0, 0])
        self.assertAlmostEqual(metrics["purity"], 0.5)
        self.assertAlmostEqual(metrics["ari"], 0.0)
        self.assertEqual(metrics["n_clusters"], 1)

    def test_noise_fraction_is_reported(self):
        metrics = clustering_metrics([0, 0, 1, 1, 2], [0, 0, -1, -1, 2])
        self.assertAlmostEqual(metrics["noise_fraction"], 0.4)

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            clustering_metrics([0, 1], [0])


class DuplicateMetricTests(unittest.TestCase):
    def test_precision_recall_f1(self):
        true_pairs = {("a", "b"), ("c", "d"), ("e", "f")}
        predicted = {("a", "b"), ("c", "d"), ("x", "y")}
        metrics = duplicate_pair_metrics(predicted, true_pairs)
        self.assertEqual(metrics["tp"], 2)
        self.assertEqual(metrics["fp"], 1)
        self.assertEqual(metrics["fn"], 1)
        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertAlmostEqual(metrics["recall"], 2 / 3)
        self.assertAlmostEqual(metrics["f1"], 2 / 3)

    def test_empty_prediction_scores_zero(self):
        metrics = duplicate_pair_metrics(set(), {("a", "b")})
        self.assertEqual(metrics["f1"], 0.0)
        self.assertEqual(metrics["fn"], 1)

    def test_true_pairs_come_from_groups(self):
        pairs = true_duplicate_pairs(["a", "b", "c", "d"], ["g1", "g1", "g1", "g2"])
        self.assertEqual(pairs, {("a", "b"), ("b", "c"), ("a", "c")})


class ClusteringRunnerTests(unittest.TestCase):
    def setUp(self):
        # Blobs sit away from the origin: L2 normalisation keeps their directions
        # separate, whereas a blob around zero would be normalised into noise.
        rng = np.random.default_rng(0)
        left = rng.normal(loc=-5.0, scale=0.02, size=(20, 4))
        right = rng.normal(loc=5.0, scale=0.02, size=(20, 4))
        self.vectors = np.vstack([left, right]).astype(np.float32)
        self.truth = ["a"] * 20 + ["b"] * 20

    def test_kmeans_recovers_separated_groups(self):
        labels = run_clustering(self.vectors, "kmeans", n_clusters=2)
        self.assertAlmostEqual(clustering_metrics(self.truth, labels)["ari"], 1.0)

    def test_hdbscan_returns_noise_label_for_sparse_points(self):
        labels = run_clustering(self.vectors, "hdbscan")
        self.assertEqual(len(labels), len(self.vectors))
        self.assertTrue(set(labels).issubset({-1, 0, 1}))

    def test_unknown_algorithm_is_rejected(self):
        with self.assertRaises(ValueError):
            run_clustering(self.vectors, "dbscan-ish")


class TfidfEncoderTests(unittest.TestCase):
    def test_encodes_normalised_dense_vectors(self):
        texts = [
            "handpump is dry in the ward",
            "no water from the handpump",
            "school has no toilet for girls",
            "girls toilet locked at school",
            "pension not received for months",
            "old age pension delayed",
            "pension pending at the bank",
            "road culvert collapsed in monsoon",
            "bridge broken on the link road",
            "ration dealer gives less weight",
        ]
        encoder = TfidfEncoder(n_components=8, min_df=1).fit(texts)
        vectors = encoder.encode(texts)
        self.assertEqual(vectors.shape[0], len(texts))
        self.assertTrue(np.isfinite(vectors).all())
        norms = np.linalg.norm(vectors, axis=1)
        self.assertTrue(np.allclose(norms, 1.0, atol=1e-5))

    def test_rejects_documents_with_no_surviving_terms(self):
        # The first three documents share their terms; the last one contributes
        # only singletons, so min_df=2 drops every term it has.
        texts = ["water supply", "water supply", "water supply", "zebra quokka"]
        encoder = TfidfEncoder(min_df=2).fit(texts)
        with self.assertRaisesRegex(ValueError, "zero TF-IDF features"):
            encoder.encode(texts)

    def test_requires_fit_before_encode(self):
        encoder = TfidfEncoder()
        with self.assertRaises(RuntimeError):
            encoder.encode(["hello"])

    def test_build_encoder_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            build_encoder("word2vec")


if __name__ == "__main__":
    unittest.main()
