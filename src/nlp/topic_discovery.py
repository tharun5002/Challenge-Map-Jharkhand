"""Sentence-embedding topic groups and intrinsic clustering metrics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score

from src.nlp.embeddings import SentenceEncoder, encode_complaints
from src.nlp.text_preparation import normalize_complaint_text


def cluster_sentence_embeddings(
    complaint_texts: Sequence[object],
    embeddings: np.ndarray,
    n_clusters: int,
    *,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float | None]]:
    """Cluster multilingual embeddings and summarize measurable model outputs."""
    texts = [normalize_complaint_text(text) for text in complaint_texts]
    if len(texts) < 3:
        raise ValueError("At least three non-empty complaints are required.")
    if any(not text for text in texts):
        raise ValueError("Complaint text must not contain empty values.")
    if (
        isinstance(n_clusters, bool)
        or not isinstance(n_clusters, int)
        or not 2 <= n_clusters < len(texts)
    ):
        raise ValueError(
            "n_clusters must be an integer between 2 and one less than "
            "the number of complaints."
        )
    if isinstance(random_state, bool) or not isinstance(random_state, int):
        raise ValueError("random_state must be an integer.")

    vectors = np.asarray(embeddings, dtype=np.float32)
    if (
        vectors.ndim != 2
        or vectors.shape[0] != len(texts)
        or vectors.shape[1] == 0
    ):
        raise ValueError("Embeddings must have one non-empty vector per complaint.")
    if not np.isfinite(vectors).all():
        raise ValueError("Embeddings must contain only finite values.")

    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0):
        raise ValueError("Embeddings must not contain zero-length vectors.")
    unit_vectors = vectors / norms[:, np.newaxis]
    distinct_vector_count = np.unique(unit_vectors, axis=0).shape[0]
    if distinct_vector_count < n_clusters:
        raise ValueError(
            f"Requested {n_clusters} clusters, but the embeddings contain only "
            f"{distinct_vector_count} distinct vectors."
        )

    labels = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=10,
    ).fit_predict(unit_vectors)

    assignments = pd.DataFrame(
        {
            "complaint_text": texts,
            "topic_id": labels.astype(int),
        }
    )
    cluster_similarities = np.empty(len(texts), dtype=np.float32)
    summaries: list[dict[str, object]] = []
    for topic_id in sorted(np.unique(labels)):
        member_indexes = np.flatnonzero(labels == topic_id)
        member_vectors = unit_vectors[member_indexes]
        center = member_vectors.mean(axis=0)
        center_norm = np.linalg.norm(center)
        if center_norm:
            center = center / center_norm
            similarities = member_vectors @ center
        else:
            similarities = np.zeros(len(member_indexes), dtype=np.float32)
        cluster_similarities[member_indexes] = similarities

        representative_order = np.argsort(-similarities, kind="stable")[:3]
        representative_texts = [
            texts[member_indexes[position]] for position in representative_order
        ]
        summaries.append(
            {
                "topic_id": int(topic_id),
                "complaints": int(len(member_indexes)),
                "representative_complaints": " | ".join(representative_texts),
            }
        )

    assignments["cluster_similarity"] = np.round(cluster_similarities, 4)
    metrics: dict[str, float | None] = {
        "silhouette_cosine": None,
        "davies_bouldin": None,
    }
    distinct_labels = np.unique(labels)
    if 1 < len(distinct_labels) < len(texts):
        metrics["silhouette_cosine"] = float(
            silhouette_score(unit_vectors, labels, metric="cosine")
        )
        metrics["davies_bouldin"] = float(
            davies_bouldin_score(unit_vectors, labels)
        )

    return assignments, pd.DataFrame(summaries), metrics


def discover_sentence_topics(
    complaint_texts: Sequence[object],
    encoder: SentenceEncoder,
    n_clusters: int,
    *,
    batch_size: int = 32,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float | None]]:
    """Encode complaint text and return its K-Means topics and measured metrics."""
    embeddings = encode_complaints(
        encoder,
        complaint_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
    )
    return cluster_sentence_embeddings(
        complaint_texts,
        embeddings,
        n_clusters,
        random_state=random_state,
    )
