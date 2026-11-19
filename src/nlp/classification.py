"""Supervised domain routing: the measured alternative to unsupervised clustering.

Clustering answers "what topics exist?". Routing answers "which desk does this
report belong to?" — the question the product must answer for a new complaint.
On this corpus the lexical baseline clusters poorly (see docs/RESULTS.md) while a
linear classifier over the same features separates domains well, so both numbers
are reported instead of quietly reporting whichever one looks better.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline

from src.nlp.text_preparation import prepare_text_for_tfidf


def train_domain_classifier(
    texts: Sequence[object],
    labels: Sequence[object],
    *,
    random_state: int = 42,
    max_iter: int = 1_000,
) -> Pipeline:
    """Fit TF-IDF + logistic regression on complaint text and its domain."""
    if len(texts) != len(labels):
        raise ValueError("texts and labels must have the same length")
    if len(texts) < 2:
        raise ValueError("at least two labelled complaints are required")

    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=prepare_text_for_tfidf,
                    token_pattern=r"\S+",
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=max_iter, random_state=random_state),
            ),
        ]
    )
    model.fit(list(texts), list(labels))
    return model


def evaluate_classifier(
    train_texts: Sequence[object],
    train_labels: Sequence[object],
    test_texts: Sequence[object],
    test_labels: Sequence[object],
    *,
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit on train, score on test, and return accuracy plus per-class metrics."""
    model = train_domain_classifier(train_texts, train_labels, random_state=random_state)
    predictions = model.predict(list(test_texts))
    report = classification_report(
        list(test_labels), predictions, output_dict=True, zero_division=0
    )

    per_class = {
        label: {name: round(float(value), 4) for name, value in stats.items()}
        for label, stats in report.items()
        if isinstance(stats, dict) and label not in {"macro avg", "weighted avg"}
    }
    return {
        "train_rows": int(len(train_texts)),
        "test_rows": int(len(test_texts)),
        "accuracy": round(float(report["accuracy"]), 4),
        "macro_f1": round(float(report["macro avg"]["f1-score"]), 4),
        "weighted_f1": round(float(report["weighted avg"]["f1-score"]), 4),
        "per_class": per_class,
        "predictions": [str(label) for label in predictions],
    }
