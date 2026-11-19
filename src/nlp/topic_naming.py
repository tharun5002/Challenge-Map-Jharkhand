"""c-TF-IDF cluster naming.

Clusters come out as integers; a person needs words. c-TF-IDF scores a term by
its frequency inside one cluster against its frequency across every cluster, so
a term that characterises a cluster ranks first even when it is rare corpus-wide.

This is the naming stage only: it assigns labels to clusters found elsewhere. It
never feeds the clustering itself, so naming cannot inflate the ARI/NMI numbers.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from src.nlp.text_preparation import prepare_text_for_tfidf

# Function words plus the duration and place-holder vocabulary every complaint
# shares. They say when a report was filed, not what it is about, so they would
# otherwise head every cluster's term list.
_EXTRA_STOP_WORDS = (
    "hai", "hain", "tha", "thi", "se", "ka", "ki", "ke", "ko", "mein", "par",
    "aur", "nahi", "koi", "log", "gaon", "bahut", "ab", "bhi", "kar", "kiya",
    "rahe", "raha", "hua", "hui", "gaya", "gayi", "liye", "kuch", "yeh", "woh",
    "है", "हैं", "था", "थी", "से", "का", "की", "के", "को", "में", "पर", "और",
    "नहीं", "कोई", "लोग", "गाँव", "बहुत", "अब", "भी", "कर", "किया", "रहे",
    "रहा", "हुआ", "हुई", "गया", "गई", "लिए", "कुछ", "यह", "वह", "कृपया",
    "ध्यान", "बात", "बनी", "अब", "दिया", "दी",
    "two", "three", "four", "six", "eight", "one", "month", "months", "week",
    "weeks", "year", "years", "ago", "since", "since", "last", "monsoon",
    "village", "people", "ward", "complaint", "complaints", "problem",
    "reported", "report", "complaining", "again", "time", "times", "nothing",
    "nobody", "several", "same", "area", "condition", "situation",
    "दो", "तीन", "चार", "छह", "आठ", "एक", "साल", "महीने", "हफ्ते", "मानसून",
    "पिछले", "शिकायत", "समस्या",
)

STOP_WORDS = sorted(set(ENGLISH_STOP_WORDS).union(_EXTRA_STOP_WORDS))


def c_tf_idf(
    texts: Sequence[object],
    labels: Sequence[object],
    *,
    top_n: int = 8,
    min_df: int = 1,
    max_features: int = 20_000,
) -> pd.DataFrame:
    """Score terms per cluster and return the strongest ``top_n`` for each."""
    prepared = [prepare_text_for_tfidf(text) for text in texts]
    cluster_labels = np.asarray(list(labels))
    if len(prepared) < 2:
        raise ValueError("at least two documents are required to name clusters")
    if len(cluster_labels) != len(prepared):
        raise ValueError("texts and labels must have the same length")
    if any(not text for text in prepared):
        raise ValueError("documents must not be empty")

    vectorizer = CountVectorizer(
        token_pattern=r"\S+",  # Unicode words, not \w chunks: Devanagari marks
        stop_words=STOP_WORDS,
        min_df=min_df,
        max_features=max_features,
        lowercase=False,
    )
    counts = vectorizer.fit_transform(prepared)
    if counts.shape[1] == 0:
        raise ValueError("no terms survived stop-word removal")

    cluster_ids = np.unique(cluster_labels)
    per_cluster = np.zeros((len(cluster_ids), counts.shape[1]), dtype=np.float64)
    sizes: list[int] = []
    for row, cluster in enumerate(cluster_ids):
        members = counts[cluster_labels == cluster]
        per_cluster[row] = np.asarray(members.sum(axis=0)).ravel()
        sizes.append(int(members.shape[0]))

    # Classic c-TF-IDF: term frequency inside the cluster times the inverse
    # frequency of that term across all clusters.
    term_frequency = per_cluster / np.maximum(per_cluster.sum(axis=1, keepdims=True), 1.0)
    total_frequency = per_cluster.sum(axis=0)
    average_words = max(float(per_cluster.sum(axis=1).mean()), 1.0)
    inverse_frequency = np.log(1.0 + average_words / np.maximum(total_frequency, 1.0))
    weights = term_frequency * inverse_frequency

    vocabulary = vectorizer.get_feature_names_out()
    rows: list[dict[str, object]] = []
    for row, cluster in enumerate(cluster_ids):
        order = np.argsort(-weights[row])[:top_n]
        terms = [str(vocabulary[index]) for index in order if weights[row][index] > 0]
        rows.append(
            {
                "cluster": int(cluster),
                "size": sizes[row],
                "top_terms": terms,
                "terms": " | ".join(terms),
            }
        )
    return pd.DataFrame(rows)


def name_clusters(
    texts: Sequence[object],
    labels: Sequence[object],
    *,
    top_n: int = 8,
) -> pd.DataFrame:
    """Return one human-readable name per cluster, ordered by cluster id."""
    named = c_tf_idf(texts, labels, top_n=top_n)
    named["label"] = named["top_terms"].map(lambda terms: ", ".join(terms[:3]))
    return named
