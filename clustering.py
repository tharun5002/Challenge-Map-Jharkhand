"""Text preprocessing, topic tagging, and unsupervised complaint clustering."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

from src.nlp.text_preparation import prepare_text_for_tfidf


TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Water": (
        "water",
        "drinking",
        "well",
        "wells",
        "hand pump",
        "hand pumps",
        "borewell",
        "borewells",
        "tap",
        "taps",
        "pump",
        "pumps",
    ),
    "Education": (
        "school",
        "schools",
        "teacher",
        "teachers",
        "classroom",
        "classrooms",
        "student",
        "students",
        "education",
        "learning",
        "college",
    ),
    "Healthcare": (
        "doctor",
        "doctors",
        "hospital",
        "hospitals",
        "health centre",
        "health centres",
        "health center",
        "health centers",
        "clinic",
        "clinics",
        "nurse",
        "nurses",
        "medicine",
        "medicines",
        "ambulance",
        "ambulances",
        "patient",
        "patients",
        "treatment",
        "medical",
    ),
    "Infrastructure": (
        "road",
        "roads",
        "pothole",
        "potholes",
        "bridge",
        "bridges",
        "bus",
        "buses",
        "transport",
        "street light",
        "street lights",
        "streetlight",
        "culvert",
        "culverts",
    ),
    "Sanitation": (
        "garbage",
        "waste",
        "drain",
        "drains",
        "sewage",
        "toilet",
        "toilets",
        "rubbish",
        "sanitation",
        "dustbin",
        "dustbins",
    ),
    "Agriculture": (
        "farmer",
        "farmers",
        "crop",
        "crops",
        "irrigation",
        "canal",
        "canals",
        "seed",
        "seeds",
        "fertilizer",
        "fertilizers",
        "sowing",
        "field",
        "fields",
        "harvest",
    ),
    "Electricity": (
        "electricity",
        "power",
        "transformer",
        "transformers",
        "outage",
        "outages",
        "blackout",
    ),
    "Internet & connectivity": (
        "internet",
        "mobile",
        "network",
        "networks",
        "signal",
        "signals",
        "broadband",
        "connectivity",
    ),
}

URGENCY_PATTERN = re.compile(
    r"\b(urgent|emergency|unsafe|critical|severe|failed|broken|"
    r"collapsed|contaminated|no drinking water|no doctors?|no teachers?|"
    r"life[- ]threatening|not working)\b",
    flags=re.IGNORECASE,
)


def clean_report_text(value: object) -> str:
    """Normalize casing and punctuation while retaining Unicode letters."""
    return prepare_text_for_tfidf(value)


def classify_topic(value: object) -> str:
    """Assign a readable topic using a small, transparent Jharkhand issue taxonomy."""
    text = clean_report_text(value)
    scores = {
        topic: sum(
            len(re.findall(rf"(?<!\w){re.escape(keyword)}(?!\w)", text))
            for keyword in keywords
        )
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    best_topic = max(scores, key=scores.get)
    return best_topic if scores[best_topic] else "Other"


def prioritize_topics(reports: pd.DataFrame, text_column: str) -> pd.DataFrame:
    """Rank topics by complaint volume and the share containing urgency signals."""
    if reports.empty:
        return pd.DataFrame(
            columns=["topic", "complaints", "urgent_reports", "priority_score", "priority"]
        )

    working = reports[[text_column]].copy()
    working["topic"] = working[text_column].map(classify_topic)
    working["urgent"] = working[text_column].fillna("").astype(str).map(
        lambda value: bool(URGENCY_PATTERN.search(value))
    )
    priorities = (
        working.groupby("topic", as_index=False)
        .agg(complaints=("urgent", "size"), urgent_reports=("urgent", "sum"))
        .sort_values("complaints", ascending=False)
    )
    max_count = max(int(priorities["complaints"].max()), 1)
    urgency_share = priorities["urgent_reports"] / priorities["complaints"]
    priorities["priority_score"] = (
        100
        * (
            0.65 * priorities["complaints"] / max_count
            + 0.35 * urgency_share
        )
    ).round(1)
    priorities["priority"] = np.select(
        [priorities["priority_score"] >= 75, priorities["priority_score"] >= 50],
        ["High", "Medium"],
        default="Monitor",
    )
    return priorities.sort_values(
        ["priority_score", "complaints", "topic"], ascending=[False, False, True]
    ).reset_index(drop=True)


def _fit_cluster_model(
    matrix,
    cluster_count: int,
    algorithm: str,
    dbscan_eps: float,
    dbscan_min_samples: int,
) -> np.ndarray:
    if algorithm == "K-Means":
        return KMeans(n_clusters=cluster_count, random_state=42, n_init=10).fit_predict(
            matrix
        )
    if algorithm == "Agglomerative":
        return AgglomerativeClustering(
            n_clusters=cluster_count, metric="cosine", linkage="average"
        ).fit_predict(matrix.toarray())
    if algorithm == "DBSCAN":
        return DBSCAN(
            eps=dbscan_eps,
            min_samples=dbscan_min_samples,
            metric="cosine",
        ).fit_predict(matrix)
    raise ValueError(f"Unknown clustering algorithm: {algorithm}")


def cluster_reports(
    reports: pd.DataFrame,
    text_column: str,
    cluster_count: int,
    algorithm: str = "K-Means",
    dbscan_eps: float = 0.65,
    dbscan_min_samples: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame, float | None]:
    """Vectorize reports, cluster them, and return assignments, summaries, and score."""
    if text_column not in reports.columns:
        raise ValueError(f"Text column '{text_column}' was not found.")

    cleaned = reports.copy()
    cleaned[text_column] = cleaned[text_column].fillna("").astype(str).str.strip()
    cleaned = cleaned.loc[cleaned[text_column].ne("")].reset_index(drop=True)
    if len(cleaned) < 2:
        raise ValueError("At least two non-empty reports are required.")
    if not 2 <= cluster_count <= len(cleaned):
        raise ValueError("Cluster count must be between 2 and the number of reports.")
    if dbscan_eps <= 0 or dbscan_min_samples < 2:
        raise ValueError("DBSCAN epsilon must be positive and min_samples at least 2.")

    cleaned["topic"] = cleaned[text_column].map(classify_topic)
    vectorizer = TfidfVectorizer(
        preprocessor=clean_report_text,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=5000,
    )
    try:
        matrix = vectorizer.fit_transform(cleaned[text_column])
    except ValueError as error:
        raise ValueError(
            "The reports do not contain enough usable words after preprocessing."
        ) from error

    assignments = _fit_cluster_model(
        matrix, cluster_count, algorithm, dbscan_eps, dbscan_min_samples
    )
    cleaned["cluster"] = assignments
    terms = vectorizer.get_feature_names_out()
    summaries = []
    similarities = np.full(len(cleaned), np.nan)

    for cluster_id in sorted(set(assignments)):
        member_indexes = np.flatnonzero(assignments == cluster_id)
        member_matrix = matrix[member_indexes]
        center = np.asarray(member_matrix.mean(axis=0)).ravel()
        top_indexes = center.argsort()[::-1][:6]
        topics = cleaned.loc[member_indexes, "topic"]
        dominant_topic = topics.value_counts().index[0]
        group_name = (
            "Noise / unassigned"
            if cluster_id == -1
            else f"{dominant_topic} · group {cluster_id + 1}"
        )
        if cluster_id != -1:
            similarities[member_indexes] = cosine_similarity(
                member_matrix, center.reshape(1, -1)
            ).ravel()

        summary = {
            "cluster": int(cluster_id),
            "group": group_name,
            "topic": dominant_topic,
            "reports": len(member_indexes),
            "top_terms": ", ".join(terms[top_indexes]),
            "representative_complaints": " | ".join(
                cleaned.loc[member_indexes, text_column].head(2).tolist()
            ),
        }
        if "district" in cleaned.columns:
            summary["districts"] = ", ".join(
                sorted(cleaned.loc[member_indexes, "district"].dropna().astype(str).unique())
            )
        summaries.append(summary)

    cleaned["cluster_similarity"] = np.round(similarities, 3)
    summary_frame = pd.DataFrame(summaries)
    scored_indexes = np.flatnonzero(assignments != -1)
    scored_assignments = assignments[scored_indexes]
    score = None
    if 1 < len(set(scored_assignments)) < len(scored_assignments):
        score = float(
            silhouette_score(
                matrix[scored_indexes], scored_assignments, metric="cosine"
            )
        )
    return cleaned, summary_frame, score


def compare_algorithms(
    reports: pd.DataFrame,
    text_column: str,
    cluster_count: int,
    dbscan_eps: float = 0.65,
    dbscan_min_samples: int = 2,
) -> pd.DataFrame:
    """Run all supported algorithms with the same text and summarize their results."""
    rows = []
    for algorithm in ("K-Means", "Agglomerative", "DBSCAN"):
        clustered, summary, score = cluster_reports(
            reports,
            text_column,
            cluster_count,
            algorithm=algorithm,
            dbscan_eps=dbscan_eps,
            dbscan_min_samples=dbscan_min_samples,
        )
        rows.append(
            {
                "algorithm": algorithm,
                "groups": int((summary["cluster"] != -1).sum()),
                "noise reports": int((clustered["cluster"] == -1).sum()),
                "silhouette score": None if score is None else round(score, 3),
            }
        )
    return pd.DataFrame(rows)
