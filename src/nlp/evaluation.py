"""Evaluation metrics and runners for clustering and deduplication.

The project's earlier metrics were intrinsic only (silhouette, Davies-Bouldin),
which cannot say whether the *topics* are right. Everything here compares
predictions against labels: ARI, NMI and purity for clustering, and
precision/recall/F1 for duplicate pairs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, HDBSCAN, KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    davies_bouldin_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.preprocessing import normalize


def purity_score(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    """Fraction of items in the majority true class of their predicted cluster."""
    frame = pd.DataFrame({"true": np.asarray(y_true), "pred": np.asarray(y_pred)})
    if frame.empty:
        raise ValueError("purity requires at least one item")
    contingency = pd.crosstab(frame["true"], frame["pred"])
    return float(contingency.max(axis=0).sum() / contingency.to_numpy().sum())


def clustering_metrics(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
) -> dict[str, float | int]:
    """Agreement between predicted clusters and ground-truth labels."""
    truth = np.asarray(y_true)
    prediction = np.asarray(y_pred)
    if truth.shape != prediction.shape:
        raise ValueError("y_true and y_pred must have the same length")
    if truth.size < 2:
        raise ValueError("at least two items are required")

    labels = np.unique(prediction)
    noise = prediction == -1
    return {
        "ari": float(adjusted_rand_score(truth, prediction)),
        "nmi": float(normalized_mutual_info_score(truth, prediction)),
        "purity": purity_score(truth, prediction),
        "n_clusters": int(len(labels)),
        "noise_fraction": float(noise.mean()) if noise.any() else 0.0,
    }


def run_clustering(
    vectors: np.ndarray,
    algorithm: str,
    *,
    n_clusters: int | None = None,
    random_state: int = 42,
) -> np.ndarray:
    """Cluster L2-normalised vectors with one of the compared algorithms."""
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] == 0:
        raise ValueError("vectors must be a 2-D non-empty matrix")
    matrix = normalize(matrix, norm="l2", axis=1)

    normalized_algorithm = algorithm.strip().lower()
    if normalized_algorithm == "kmeans":
        if not n_clusters:
            raise ValueError("kmeans requires n_clusters")
        return KMeans(
            n_clusters=n_clusters, random_state=random_state, n_init=10
        ).fit_predict(matrix)
    if normalized_algorithm == "agglomerative":
        if not n_clusters:
            raise ValueError("agglomerative requires n_clusters")
        return AgglomerativeClustering(
            n_clusters=n_clusters, metric="cosine", linkage="average"
        ).fit_predict(matrix)
    if normalized_algorithm == "hdbscan":
        return HDBSCAN(min_cluster_size=15, min_samples=5, metric="euclidean").fit_predict(
            matrix
        )
    raise ValueError("algorithm must be kmeans, agglomerative or hdbscan")


def evaluate_clustering(
    texts: Sequence[str],
    y_true: Sequence[Any],
    encoder: Any,
    algorithm: str,
    *,
    n_clusters: int | None = None,
    random_state: int = 42,
    silhouette_sample: int = 2_000,
) -> dict[str, float | int | str]:
    """Encode, cluster and score against labels in one call."""
    vectors = encoder.encode(list(texts))
    predictions = run_clustering(
        vectors, algorithm, n_clusters=n_clusters, random_state=random_state
    )
    result: dict[str, float | int | str] = {
        "encoder": getattr(encoder, "name", encoder.__class__.__name__),
        "algorithm": algorithm,
        "items": int(len(predictions)),
    }
    result.update(clustering_metrics(y_true, predictions))

    distinct = np.unique(predictions)
    if 1 < len(distinct) < len(predictions):
        sample_size = max(2, min(silhouette_sample, len(predictions) - 1))
        result["silhouette"] = float(
            silhouette_score(
                vectors,
                predictions,
                metric="cosine",
                sample_size=sample_size,
                random_state=random_state,
            )
        )
        result["davies_bouldin"] = float(davies_bouldin_score(vectors, predictions))
    else:
        result["silhouette"] = float("nan")
        result["davies_bouldin"] = float("nan")
    return result


def duplicate_pair_metrics(
    predicted_pairs: set[tuple[str, str]],
    true_pairs: set[tuple[str, str]],
) -> dict[str, float | int]:
    """Precision, recall and F1 over unordered complaint pairs."""
    true_positive = len(predicted_pairs & true_pairs)
    false_positive = len(predicted_pairs - true_pairs)
    false_negative = len(true_pairs - predicted_pairs)
    precision = true_positive / (true_positive + false_positive) if predicted_pairs else 0.0
    recall = true_positive / len(true_pairs) if true_pairs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_pairs": len(true_pairs),
        "predicted_pairs": len(predicted_pairs),
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def true_duplicate_pairs(
    complaint_ids: Sequence[str],
    duplicate_groups: Sequence[str],
) -> set[tuple[str, str]]:
    """All pairs that share a duplicate group."""
    groups: dict[str, list[str]] = {}
    for complaint_id, group in zip(complaint_ids, duplicate_groups):
        groups.setdefault(str(group), []).append(str(complaint_id))

    pairs: set[tuple[str, str]] = set()
    for members in groups.values():
        ordered = sorted(members)
        for left in range(len(ordered) - 1):
            for right in range(left + 1, len(ordered)):
                pairs.add((ordered[left], ordered[right]))
    return pairs


def _top_k_pairs(
    similarity: np.ndarray,
    neighbours: int,
    lower_bound: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return local (row, column, similarity) for each row's top-k neighbours."""
    size = similarity.shape[0]
    k = max(1, min(neighbours, size - 1))
    working = similarity.copy()
    np.fill_diagonal(working, -np.inf)
    top = np.argpartition(-working, kth=k - 1, axis=1)[:, :k]
    values = np.take_along_axis(working, top, axis=1)
    rows = np.repeat(np.arange(size), k).reshape(size, k)
    keep = values >= lower_bound
    return rows[keep], top[keep], values[keep]


def sweep_duplicate_thresholds(
    complaint_ids: Sequence[str],
    texts: Sequence[str],
    districts: Sequence[str],
    duplicate_groups: Sequence[str],
    encoder: Any,
    thresholds: Sequence[float],
    *,
    neighbours: int = 5,
    sparse: bool = True,
) -> pd.DataFrame:
    """Score duplicate detection at several thresholds.

    Candidate pairs are the top-``neighbours`` within a district block, which is
    how the product actually behaves (a submitter is shown a short list, never a
    full pairwise sweep). Two complaints from different districts are never
    compared; that constraint is disclosed in the results.

    ``sparse`` uses the encoder's exact TF-IDF cosine when it offers one
    (``encode_sparse``). The SVD path is kept as an alternative but inflates
    similarities between unrelated complaints, so thresholds calibrated on it do
    not mean what they appear to mean.
    """
    ids = [str(value) for value in complaint_ids]
    district_values = [str(value) for value in districts]
    if not (len(ids) == len(texts) == len(district_values) == len(duplicate_groups)):
        raise ValueError("ids, texts, districts and duplicate groups must align")

    ordered_thresholds = sorted(float(value) for value in thresholds)
    if not ordered_thresholds:
        raise ValueError("at least one threshold is required")
    lower_bound = ordered_thresholds[0]

    encoder.fit(list(texts))
    truth = true_duplicate_pairs(ids, duplicate_groups)

    ids_array = np.asarray(ids, dtype=object)
    texts_array = np.asarray(list(texts), dtype=object)
    district_array = np.asarray(district_values)

    pair_keys: list[int] = []
    pair_similarity: list[float] = []
    total = len(ids)

    for district in np.unique(district_array):
        positions = np.flatnonzero(district_array == district)
        if len(positions) < 2:
            continue
        block_texts = [str(texts_array[position]) for position in positions]
        sparse_encoder = getattr(encoder, "encode_sparse", None)
        if sparse and callable(sparse_encoder):
            matrix = sparse_encoder(block_texts)
            similarity = np.asarray((matrix @ matrix.T).todense(), dtype=np.float32)
        else:
            vectors = np.asarray(encoder.encode(block_texts), dtype=np.float32)
            vectors = normalize(vectors, norm="l2", axis=1)
            similarity = vectors @ vectors.T
        # Cosine is in [-1, 1] by definition; float error can push an identical
        # pair to 0.9999999 and let it fail a 1.00 threshold.
        similarity = np.clip(similarity, -1.0, 1.0)

        local_rows, local_columns, local_values = _top_k_pairs(
            similarity, neighbours, lower_bound
        )
        if not len(local_rows):
            continue
        global_left = positions[local_rows]
        global_right = positions[local_columns]
        low = np.minimum(global_left, global_right)
        high = np.maximum(global_left, global_right)
        pair_keys.extend((low * total + high).tolist())
        pair_similarity.extend(local_values.tolist())

    if not pair_keys:
        empty = duplicate_pair_metrics(set(), truth)
        return pd.DataFrame([{**empty, "threshold": t} for t in ordered_thresholds])

    keys = np.asarray(pair_keys, dtype=np.int64)
    sims = np.asarray(pair_similarity, dtype=np.float32)
    # A symmetric top-k list yields each unordered pair twice; keep one copy.
    unique_keys, first_index = np.unique(keys, return_index=True)
    unique_sims = np.round(sims[first_index], 6)

    left_index = unique_keys // total
    right_index = unique_keys % total
    group_by_id = dict(zip(ids, (str(value) for value in duplicate_groups)))
    left_groups = [group_by_id[ids[index]] for index in left_index]
    right_groups = [group_by_id[ids[index]] for index in right_index]
    is_true = np.fromiter(
        (left == right for left, right in zip(left_groups, right_groups)),
        dtype=bool,
        count=len(unique_keys),
    )
    truth_count = len(truth)

    rows: list[dict[str, float | int]] = []
    for threshold in ordered_thresholds:
        selected = unique_sims >= threshold
        predicted = int(selected.sum())
        true_positive = int((selected & is_true).sum())
        false_positive = predicted - true_positive
        false_negative = truth_count - true_positive
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / truth_count if truth_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append(
            {
                "threshold": threshold,
                "true_pairs": truth_count,
                "predicted_pairs": predicted,
                "tp": true_positive,
                "fp": false_positive,
                "fn": false_negative,
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
            }
        )
    return pd.DataFrame(rows)
