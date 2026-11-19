import unittest

import numpy as np
import pandas as pd

from src.nlp.classification import evaluate_classifier, train_domain_classifier
from src.nlp.matching import (
    DEFAULT_WEIGHTS as MATCHING_WEIGHTS,
    ChallengeProfile,
    PartnerProfile,
    rank_matches,
    score_match,
)
from src.nlp.priority import (
    DEFAULT_WEIGHTS as PRIORITY_WEIGHTS,
    score_priorities,
    validate_weights,
)
from src.nlp.topic_naming import name_clusters
from src.nlp.vectorizers import TfidfEncoder


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame(
            {
                "challenge_id": ["a", "a", "b", "b", "b"],
                "severity": ["critical", "high", "low", "low", "medium"],
                "affected_population": [5000, 4000, 100, 50, 80],
                "district": ["Ranchi", "Ranchi", "Dumka", "Dumka", "Dumka"],
                "complaint_text": [
                    "handpump is dry",
                    "handpump is dry",
                    "school roof leaking",
                    "school roof leaking",
                    "school roof leaking",
                ],
            }
        )

    def test_scores_are_bounded_and_ranked(self):
        result = score_priorities(self.frame)
        self.assertTrue(result["priority_score"].between(0, 100).all())
        self.assertEqual(result.iloc[0]["challenge_id"], "a")
        self.assertTrue(
            list(result["priority_score"]) == sorted(result["priority_score"], reverse=True)
        )

    def test_breakdown_reconstructs_the_score(self):
        result = score_priorities(self.frame).set_index("challenge_id")
        breakdown = result.loc["a", "priority_breakdown"]
        weights = breakdown["weights"]
        rebuilt = 100 * sum(weights[name] * breakdown[name] for name in weights)
        self.assertAlmostEqual(rebuilt, result.loc["a", "priority_score"], places=1)

    def test_recurrence_counts_repeated_reports(self):
        result = score_priorities(self.frame).set_index("challenge_id")
        self.assertAlmostEqual(result.loc["a", "recurrence_component"], 0.5)
        self.assertAlmostEqual(result.loc["b", "recurrence_component"], 2 / 3)

    def test_weight_validation(self):
        with self.assertRaisesRegex(ValueError, "Missing weight"):
            validate_weights({"severity": 0.5})
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            validate_weights({**PRIORITY_WEIGHTS, "severity": 0.5})
        with self.assertRaisesRegex(ValueError, "Unknown weight"):
            validate_weights({**PRIORITY_WEIGHTS, "novelty": 0.0})

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            score_priorities(self.frame[["challenge_id", "severity"]])


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.challenge = ChallengeProfile(
            challenge_id="c1",
            capability_tags=frozenset({"water", "civil"}),
            districts=frozenset({"Ranchi", "Khunti"}),
            severity_score=0.8,
        )
        self.partners = [
            PartnerProfile(
                organization_id="p1",
                name="BIT Mesra Civil",
                capability_tags=frozenset({"water", "civil"}),
                districts=frozenset({"Ranchi"}),
                capacity=0.9,
            ),
            PartnerProfile(
                organization_id="p2",
                name="Dumka NGO",
                capability_tags=frozenset({"water"}),
                districts=frozenset({"Dumka"}),
                capacity=0.6,
            ),
            PartnerProfile(
                organization_id="p3",
                name="Agri Lab",
                capability_tags=frozenset({"agriculture"}),
                districts=frozenset({"Dumka"}),
                capacity=1.0,
            ),
        ]

    def test_ranking_prefers_matching_capability_and_district(self):
        ranked = rank_matches(self.challenge, self.partners, top_k=3)
        self.assertEqual(ranked.iloc[0]["organization_id"], "p1")
        self.assertGreater(ranked.iloc[0]["score"], ranked.iloc[-1]["score"])
        self.assertEqual(
            set(ranked.iloc[0]["breakdown"]), {"components", "weighted", "weights"}
        )

    def test_top_k_truncates(self):
        self.assertEqual(len(rank_matches(self.challenge, self.partners, top_k=2)), 2)

    def test_unrelated_partner_keeps_only_severity_and_capacity(self):
        scored = score_match(self.challenge, self.partners[2])
        self.assertEqual(scored["components"]["tag_overlap"], 0.0)
        self.assertEqual(scored["components"]["district_proximity"], 0.0)
        expected = MATCHING_WEIGHTS["severity"] * 0.8 + MATCHING_WEIGHTS["capacity"] * 1.0
        self.assertAlmostEqual(scored["score"], expected, places=4)

    def test_distance_decay_used_when_supplied(self):
        far = score_match(self.challenge, self.partners[2], distance_km=150.0)
        self.assertGreater(far["components"]["district_proximity"], 0.0)
        self.assertLess(far["components"]["district_proximity"], 1.0)

    def test_matching_weight_validation(self):
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            score_match(
                self.challenge,
                self.partners[0],
                weights={**MATCHING_WEIGHTS, "tag_overlap": 0.9},
            )


class TopicNamingTests(unittest.TestCase):
    def test_distinct_clusters_get_distinct_terms(self):
        texts = [
            "handpump is dry in ranchi",
            "no water from the handpump",
            "school has no teacher",
            "teacher absent in school",
        ]
        named = name_clusters(texts, [0, 0, 1, 1], top_n=4).set_index("cluster")
        self.assertIn("handpump", named.loc[0, "terms"])
        self.assertIn("teacher", named.loc[1, "terms"])
        self.assertNotEqual(named.loc[0, "terms"], named.loc[1, "terms"])

    def test_rejects_misaligned_input(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            name_clusters(["one two", "three four"], [0])


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.water = [f"the handpump in ward {index} is dry" for index in range(20)]
        self.school = [f"the school in ward {index} has no teacher" for index in range(20)]
        self.texts = self.water + self.school
        self.labels = ["water"] * 20 + ["school"] * 20

    def test_separable_corpus_is_classified(self):
        model = train_domain_classifier(self.texts, self.labels)
        predictions = model.predict(["handpump dry again", "teacher absent at school"])
        self.assertEqual(list(predictions), ["water", "school"])

    def test_metrics_are_reported(self):
        metrics = evaluate_classifier(self.texts, self.labels, self.texts, self.labels)
        self.assertAlmostEqual(metrics["accuracy"], 1.0)
        self.assertAlmostEqual(metrics["macro_f1"], 1.0)
        self.assertIn("water", metrics["per_class"])
        self.assertEqual(metrics["test_rows"], len(self.texts))


class BoilerplateFilterTests(unittest.TestCase):
    def test_terms_shared_by_most_documents_are_dropped(self):
        # Each document needs one token of its own, or the boilerplate filter
        # would empty it and (correctly) back off.
        documents = [
            f"boilerplate sentence about the local office serial{index}"
            for index in range(120)
        ] + [f"token{index} broken" for index in range(40)]
        encoder = TfidfEncoder(min_df=1, n_components=8).fit(documents)
        vocabulary = set(encoder._vectorizer.get_feature_names_out())
        self.assertNotIn("boilerplate", vocabulary)
        self.assertIn("token7", vocabulary)
        self.assertAlmostEqual(encoder.fitted_max_df, 0.03, places=6)

    def test_small_corpora_skip_the_filter(self):
        encoder = TfidfEncoder(min_df=1).fit(
            ["water supply dry", "water supply dry", "road repair pending"]
        )
        self.assertIn("water", set(encoder._vectorizer.get_feature_names_out()))

    def test_encode_sparse_returns_unit_rows(self):
        encoder = TfidfEncoder(min_df=1).fit(
            ["alpha beta", "beta gamma", "gamma delta"]
        )
        matrix = encoder.encode_sparse(["alpha beta", "beta gamma"])
        self.assertEqual(matrix.shape[0], 2)
        norms = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel())
        self.assertTrue(np.allclose(norms, 1.0))

    def test_empty_vocabulary_backs_off_instead_of_dropping_documents(self):
        # Every term is shared by every document, so a 3% filter would keep
        # nothing at all. The filter must loosen rather than leave a corpus of
        # zero rows.
        documents = ["shared template words"] * 120
        encoder = TfidfEncoder(min_df=1).fit(documents)
        self.assertGreater(encoder.fitted_max_df, 0.03)
        self.assertIn("words", set(encoder._vectorizer.get_feature_names_out()))
        matrix = encoder.encode_sparse(["shared template words"])
        self.assertGreater(float(np.asarray(matrix.sum(axis=1)).ravel()[0]), 0.0)


if __name__ == "__main__":
    unittest.main()
