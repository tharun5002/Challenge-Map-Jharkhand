import unittest

import pandas as pd

from clustering import (
    classify_topic,
    clean_report_text,
    cluster_reports,
    compare_algorithms,
    prioritize_topics,
)


class ComplaintAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.reports = pd.DataFrame(
            {
                "district": ["Ranchi", "Palamu", "Godda", "Dumka", "Bokaro", "Ranchi"],
                "report_text": [
                    "No drinking water in our village.",
                    "Water supply is irregular.",
                    "Government school has no teachers.",
                    "Hospital has no doctors.",
                    "Roads are damaged.",
                    "Our hand pump has stopped working.",
                ],
            }
        )

    def test_preprocessing_and_topic_tags(self):
        self.assertEqual(clean_report_text("Roads, DAMAGED!"), "roads damaged")
        self.assertEqual(classify_topic(self.reports.loc[0, "report_text"]), "Water")
        self.assertEqual(classify_topic(self.reports.loc[2, "report_text"]), "Education")
        self.assertEqual(classify_topic(self.reports.loc[3, "report_text"]), "Healthcare")
        self.assertEqual(classify_topic(self.reports.loc[4, "report_text"]), "Infrastructure")

    def test_all_clustering_algorithms_assign_reports(self):
        for algorithm in ("K-Means", "Agglomerative", "DBSCAN"):
            with self.subTest(algorithm=algorithm):
                assignments, summary, score = cluster_reports(
                    self.reports,
                    "report_text",
                    3,
                    algorithm=algorithm,
                    dbscan_eps=0.8,
                )
                self.assertEqual(len(assignments), len(self.reports))
                self.assertIn("cluster_similarity", assignments)
                self.assertIn("representative_complaints", summary)
                self.assertIn("topic", assignments)
                self.assertTrue(score is None or -1 <= score <= 1)

    def test_comparison_and_priority_summary(self):
        comparison = compare_algorithms(self.reports, "report_text", 3)
        self.assertEqual(comparison["algorithm"].tolist(), [
            "K-Means",
            "Agglomerative",
            "DBSCAN",
        ])
        priorities = prioritize_topics(self.reports, "report_text")
        self.assertEqual(int(priorities["complaints"].sum()), len(self.reports))
        self.assertTrue(priorities["priority_score"].between(0, 100).all())


if __name__ == "__main__":
    unittest.main()
