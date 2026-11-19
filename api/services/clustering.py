"""Re-cluster stored complaints into draft challenges (plan 6.1 stages 4-8).

The job is deliberately conservative:

* only complaints with status ``pending``/``clustered`` are clustered, so merged
  duplicates and rejected reports never re-enter;
* every previous **draft** is replaced, while published challenges are never
  touched — an admin's published brief must not disappear because a nightly job
  re-ran;
* priority comes from ``src/nlp/priority.py`` and matches from
  ``src/nlp/matching.py``, both of which return their breakdowns, so every number
  this job writes can be explained later.

Embeddings are recomputed per run because Phase 2's pgvector column does not
exist yet. That is a cost, not a correctness claim.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from api.store import audit, connection, slugify, utc_now
from src.nlp.evaluation import run_clustering
from src.nlp.matching import ChallengeProfile, PartnerProfile, rank_matches
from src.nlp.priority import score_priorities
from src.nlp.text_preparation import prepare_text_for_tfidf
from src.nlp.topic_naming import name_clusters
from src.nlp.vectorizers import TfidfEncoder

MIN_COMPLAINTS = 2
MAX_MATCHES_PER_CHALLENGE = 3

# Keyword lexicon used only to tag a cluster with a domain for partner matching.
# It is a heuristic and is documented as one: an admin can rename the challenge
# afterwards, and the challenge's own terms are always shown in its summary.
DOMAIN_LEXICON: dict[str, tuple[str, ...]] = {
    "water": ("water", "handpump", "pipe", "tank", "tap", "pipeline", "well"),
    "sanitation": ("drain", "garbage", "toilet", "sewage", "waste", "nali"),
    "roads": ("road", "culvert", "bridge", "bus", "streetlight", "bitumen"),
    "electricity": ("feeder", "transformer", "voltage", "meter", "power", "bijli"),
    "health": ("doctor", "phc", "medicine", "ambulance", "health", "vaccine", "hospital"),
    "education": ("school", "teacher", "midday", "textbook", "anganwadi"),
    "food": ("ration", "pds", "grain", "dealer", "aadhaar"),
    "welfare": ("pension", "scholarship", "mgnrega", "disability", "widow"),
    "land": ("mutation", "registry", "land", "parcha", "demarcation", "dakhil"),
    "employment": ("job", "wage", "skill", "migrant", "contract"),
    "agriculture": ("canal", "irrigation", "seed", "fertiliser", "crop", "borewell", "mandi"),
    "safety": ("police", "liquor", "safety", "dust", "flood", "fraud"),
}


class NotEnoughComplaints(Exception):
    """Raised when the queue is too small to cluster honestly."""


def infer_domain(texts: list[str]) -> str:
    prepared = " ".join(prepare_text_for_tfidf(text) for text in texts)
    scores = {
        domain: sum(1 for word in words if word in prepared)
        for domain, words in DOMAIN_LEXICON.items()
    }
    best = max(scores, key=lambda name: scores[name])
    return best if scores[best] else "unassigned"


def _unique_slug(title: str, used: set[str]) -> str:
    base = slugify(title)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def recluster(
    *,
    clusters: int | None = None,
    seed: int = 42,
    actor_id: int | None = None,
) -> dict[str, int]:
    with connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT report_id, district, raw_text, severity, affected_population
                FROM complaints
                WHERE status IN ('pending', 'clustered')
                """
            ).fetchall()
        ]
    if len(rows) < MIN_COMPLAINTS:
        raise NotEnoughComplaints(
            "at least 2 pending or previously clustered complaints are required; "
            f"found {len(rows)}"
        )

    texts = [str(row["raw_text"]) for row in rows]
    encoder = TfidfEncoder(analyzer="word", ngram_range=(1, 2), min_df=1)
    encoder.fit(texts)

    requested = clusters or max(2, len(rows) // 8)
    k = max(2, min(requested, len(rows) - 1))
    labels = run_clustering(
        encoder.encode(texts), "kmeans", n_clusters=k, random_state=seed
    )
    naming = name_clusters(texts, labels, top_n=6).set_index("cluster")

    frame = pd.DataFrame(
        {
            "challenge_key": labels,
            "severity": [row["severity"] for row in rows],
            "affected_population": [row["affected_population"] or 0 for row in rows],
            "district": [row["district"] for row in rows],
            "complaint_text": texts,
        }
    )
    priorities = score_priorities(frame, group_column="challenge_key").set_index(
        "challenge_key"
    )

    created = 0
    clustered = 0
    matches_created = 0
    now = utc_now()

    with connection() as conn:
        partners = [
            dict(row)
            for row in conn.execute("SELECT * FROM organizations").fetchall()
        ]
        conn.execute("DELETE FROM challenges WHERE status = 'draft'")
        used_slugs = {
            row["slug"]
            for row in conn.execute("SELECT slug FROM challenges").fetchall()
        }

        for key in sorted(priorities.index):
            members = np.flatnonzero(labels == key)
            if not len(members):
                continue
            member_rows = [rows[int(index)] for index in members]
            cluster_texts = [str(row["raw_text"]) for row in member_rows]

            terms: list[str] = []
            if key in naming.index:
                terms = list(naming.loc[key, "top_terms"])
            title = (
                ", ".join(term.title() for term in terms[:3])
                or f"Complaint cluster {int(key) + 1}"
            )
            domain = infer_domain(cluster_texts)
            slug = _unique_slug(title, used_slugs)
            summary = "Reports sharing: " + ", ".join(terms) if terms else ""
            priority = priorities.loc[key]

            cursor = conn.execute(
                """
                INSERT INTO challenges (
                    slug, title, summary, domain, capability_tags, complaint_count,
                    affected_total, severity_score, priority_score,
                    priority_breakdown, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    slug,
                    title,
                    summary,
                    domain,
                    json.dumps([domain]),
                    int(priority["complaint_count"]),
                    int(priority["affected_total"]),
                    float(priority["severity_component"]),
                    float(priority["priority_score"]),
                    json.dumps(priority["priority_breakdown"]),
                    now,
                    now,
                ),
            )
            challenge_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT OR IGNORE INTO challenge_complaints
                    (challenge_id, complaint_report_id, similarity)
                VALUES (?, ?, 1.0)
                """,
                [(challenge_id, row["report_id"]) for row in member_rows],
            )
            for row in member_rows:
                conn.execute(
                    """
                    UPDATE complaints
                    SET status = 'clustered', updated_at = ?
                    WHERE report_id = ? AND status = 'pending'
                    """,
                    (now, row["report_id"]),
                )
            created += 1
            clustered += len(member_rows)

            if partners:
                challenge = ChallengeProfile(
                    challenge_id=slug,
                    capability_tags=frozenset({domain}),
                    districts=frozenset(str(row["district"]) for row in member_rows),
                    severity_score=float(priority["severity_component"]),
                )
                profiles = [
                    PartnerProfile(
                        organization_id=str(partner["id"]),
                        name=str(partner["name"]),
                        capability_tags=frozenset(json.loads(partner["capability_tags"])),
                        districts=frozenset(json.loads(partner["districts"])),
                        capacity=float(partner["capacity"]),
                    )
                    for partner in partners
                ]
                ranked = rank_matches(
                    challenge, profiles, top_k=MAX_MATCHES_PER_CHALLENGE
                )
                for record in ranked.to_dict(orient="records"):
                    conn.execute(
                        """
                        INSERT INTO matches (
                            challenge_id, organization_id, score, breakdown,
                            status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'suggested', ?, ?)
                        """,
                        (
                            challenge_id,
                            int(record["organization_id"]),
                            float(record["score"]),
                            json.dumps(record["breakdown"]),
                            now,
                            now,
                        ),
                    )
                    matches_created += 1

        audit(
            conn,
            actor_id=actor_id,
            action="recluster",
            entity_type="challenge",
            entity_id=None,
            payload={
                "challenges_created": created,
                "complaints_clustered": clustered,
                "matches_created": matches_created,
            },
        )

    return {
        "challenges_created": created,
        "complaints_clustered": clustered,
        "matches_created": matches_created,
    }
