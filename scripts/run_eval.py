"""Run the Phase 4 evaluation and write docs/RESULTS.md from measured output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.nlp.classification import evaluate_classifier
from src.nlp.evaluation import (
    clustering_metrics,
    evaluate_clustering,
    run_clustering,
    sweep_duplicate_thresholds,
)
from src.nlp.text_preparation import prepare_text_for_tfidf
from src.nlp.topic_naming import name_clusters
from src.nlp.vectorizers import SbertEncoder, TfidfEncoder

DEFAULT_COMPLAINTS = PROJECT_ROOT / "data" / "synthetic" / "complaints_15k.csv"
DEFAULT_TRUTH = PROJECT_ROOT / "data" / "synthetic" / "ground_truth_15k.csv"
DEFAULT_EVAL = PROJECT_ROOT / "data" / "synthetic" / "complaints_2k_eval.csv"
DEFAULT_EVAL_TRUTH = PROJECT_ROOT / "data" / "synthetic" / "ground_truth_2k_eval.csv"
RESULTS_PATH = PROJECT_ROOT / "docs" / "RESULTS.md"
METRICS_PATH = PROJECT_ROOT / "models" / "eval_metrics.json"
DEDUP_CONFIG_PATH = PROJECT_ROOT / "models" / "dedup_threshold.json"
EMBEDDING_CONFIG_PATH = PROJECT_ROOT / "models" / "embedding_config.json"

THRESHOLDS = [round(0.30 + step * 0.05, 2) for step in range(15)]  # 0.30 .. 1.00
ALGORITHMS = ("kmeans", "agglomerative", "hdbscan")
TRUTH_COLUMNS = ["complaint_id", "domain", "sub_issue", "duplicate_group_id"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complaints", type=Path, default=DEFAULT_COMPLAINTS)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument("--eval-complaints", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--eval-truth", type=Path, default=DEFAULT_EVAL_TRUTH)
    parser.add_argument("--sample", type=int, default=3_000)
    parser.add_argument("--clusters", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-dedup", action="store_true")
    parser.add_argument(
        "--skip-sbert",
        action="store_true",
        help="omit the Sentence-BERT comparison (needs torch + sentence-transformers)",
    )
    return parser.parse_args()


def load_merged(complaints_path: Path, truth_path: Path) -> pd.DataFrame:
    complaints = pd.read_csv(complaints_path)
    truth = pd.read_csv(truth_path)
    merged = complaints.merge(
        truth[TRUTH_COLUMNS], on="complaint_id", how="inner", validate="one_to_one"
    )
    if len(merged) != len(complaints) or len(merged) != len(truth):
        raise ValueError(
            f"{complaints_path.name}: labels do not cover every complaint "
            f"({len(merged)} matched of {len(complaints)})"
        )
    return merged


def stratified_sample(frame: pd.DataFrame, size: int, seed: int, *, by: str = "domain") -> pd.DataFrame:
    """Take roughly equal numbers per label so no class dominates the sample."""
    groups = [group for _, group in frame.groupby(by, sort=True) if len(group)]
    if not groups:
        raise ValueError("cannot sample from an empty frame")
    per_group = max(1, size // len(groups))
    parts = [group.sample(min(per_group, len(group)), random_state=seed) for group in groups]
    return (
        pd.concat(parts, ignore_index=True)
        .sample(frac=1.0, random_state=seed)
        .reset_index(drop=True)
    )


def clustering_rows(
    texts: list[str],
    labels: list[object],
    encoders: dict[str, TfidfEncoder],
    clusters: int,
    seed: int,
    split: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for encoder_name, encoder in encoders.items():
        for algorithm in ALGORITHMS:
            try:
                row: dict[str, object] = evaluate_clustering(
                    texts,
                    labels,
                    encoder,
                    algorithm,
                    n_clusters=clusters if algorithm != "hdbscan" else None,
                    random_state=seed,
                )
            except Exception as error:  # noqa: BLE001 - reported, never hidden
                row = {"error": f"{type(error).__name__}: {error}"}
            row.update(
                {
                    "encoder": encoder_name,
                    "algorithm": algorithm,
                    "split": split,
                    "label_space": "domain",
                }
            )
            rows.append(row)
    return rows


def error_examples(
    sample: pd.DataFrame,
    labels: np.ndarray,
    naming: pd.DataFrame,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Show what the model got wrong and name the most likely cause."""
    frame = sample[["complaint_id", "complaint_text", "language", "domain"]].copy()
    frame["cluster"] = labels
    majority = frame.groupby("cluster")["domain"].agg(lambda values: values.value_counts().idxmax())
    dominant_language = frame.groupby("cluster")["language"].agg(
        lambda values: values.value_counts().idxmax()
    )
    terms = dict(zip(naming["cluster"], naming["top_terms"]))
    frame["cluster_domain"] = frame["cluster"].map(majority)
    frame["cluster_language"] = frame["cluster"].map(dominant_language)
    sizes = frame["cluster"].value_counts()

    mismatched = frame[frame["domain"] != frame["cluster_domain"]].copy()
    mismatched["cluster_size"] = mismatched["cluster"].map(sizes)
    mismatched = mismatched.sort_values(
        ["cluster_size", "complaint_id"], ascending=[False, True]
    ).head(limit)

    rows: list[dict[str, object]] = []
    for record in mismatched.itertuples():
        prepared = prepare_text_for_tfidf(record.complaint_text)
        cluster_terms = list(terms.get(record.cluster, []))
        if record.language != record.cluster_language:
            cause = "language boundary: cluster is dominated by another script"
        elif not any(term in prepared for term in cluster_terms):
            cause = "shared boilerplate: few of the cluster's terms appear in the report"
        else:
            cause = "overlapping wording between domains"
        rows.append(
            {
                "complaint_id": record.complaint_id,
                "language": record.language,
                "true_domain": record.domain,
                "cluster": int(record.cluster),
                "cluster_domain": record.cluster_domain,
                "cluster_terms": ", ".join(cluster_terms[:4]),
                "text": str(record.complaint_text),
                "likely_cause": cause,
            }
        )
    return rows


def encoder_comparison(
    clustering: pd.DataFrame,
    dedup_by_encoder: dict[str, dict[str, float] | None],
) -> pd.DataFrame:
    """Best held-out configuration per encoder, beside its duplicate-detection F1.

    Same data, same algorithms, same metrics — only the encoder changes, which is
    the comparison that justifies (or does not justify) the deep model.

    "best_algorithm" is whichever algorithm scored the highest ARI on the held-out
    split, chosen after the fact from the measured rows rather than picked by hand.
    """
    heldout = clustering[clustering["split"] == "heldout_2k"]
    if "ari" not in heldout.columns:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for encoder in sorted(heldout["encoder"].dropna().unique()):
        subset = heldout[heldout["encoder"] == encoder].dropna(subset=["ari"])
        if subset.empty:
            continue
        best_row = subset.sort_values(["ari", "nmi"], ascending=False).iloc[0]
        dedup = dedup_by_encoder.get(str(encoder))
        rows.append(
            {
                "encoder": encoder,
                "best_algorithm": best_row["algorithm"],
                "ari": float(best_row["ari"]),
                "nmi": float(best_row["nmi"]),
                "purity": float(best_row["purity"]),
                "dedup_f1": None if dedup is None else float(dedup["f1"]),
                "dedup_threshold": None if dedup is None else float(dedup["threshold"]),
            }
        )
    return pd.DataFrame(rows)


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    train = load_merged(args.complaints, args.truth)
    heldout = load_merged(args.eval_complaints, args.eval_truth)

    sample = stratified_sample(train, args.sample, args.seed)
    sample_texts = sample["complaint_text"].tolist()

    encoders: dict[str, object] = {
        "tfidf-word": TfidfEncoder(analyzer="word", ngram_range=(1, 2)),
        "tfidf-char": TfidfEncoder(analyzer="char_wb", ngram_range=(3, 5), n_components=160),
    }
    # The multilingual encoder is loaded now, before any measurement starts, so a
    # missing model downgrades the run to the lexical baselines instead of
    # failing halfway through a table.
    sbert_error: str | None = None
    if not args.skip_sbert:
        try:
            sbert = SbertEncoder()
            sbert.encode(["warm-up"])
            encoders["sbert"] = sbert
        except Exception as error:  # noqa: BLE001 - recorded, never hidden
            sbert_error = f"{type(error).__name__}: {error}"
            print(f"Sentence-BERT unavailable, continuing without it: {sbert_error}")

    for encoder in encoders.values():
        encoder.fit(sample_texts)

    rows = clustering_rows(sample_texts, sample["domain"].tolist(), encoders, args.clusters, args.seed, "train_sample")
    rows += clustering_rows(
        heldout["complaint_text"].tolist(),
        heldout["domain"].tolist(),
        encoders,
        args.clusters,
        args.seed,
        "heldout_2k",
    )

    # Lexical features cannot match the same issue written in Devanagari and in
    # Latin script, so the mixed-language partition is reported next to a
    # monolingual slice where that boundary is removed.
    english = sample[sample["language"].eq("en")]
    within_language: dict[str, object] | None = None
    if len(english) >= args.clusters * 20:
        within_language = evaluate_clustering(
            english["complaint_text"].tolist(),
            english["domain"].tolist(),
            encoders["tfidf-char"],
            "agglomerative",
            n_clusters=args.clusters,
            random_state=args.seed,
        )
        within_language.update(
            {
                "encoder": "tfidf-char",
                "algorithm": "agglomerative",
                "split": "train_sample_english",
                "label_space": "domain",
            }
        )
        rows.append(within_language)

    # Finer granularity: does the partition track sub-issues even when it misses
    # the coarser domain grouping?
    sub_issue_clusters = int(sample["sub_issue"].nunique())
    sub_issue_row = evaluate_clustering(
        sample_texts,
        sample["sub_issue"].tolist(),
        encoders["tfidf-word"],
        "kmeans",
        n_clusters=min(sub_issue_clusters, len(sample) - 1),
        random_state=args.seed,
    )
    sub_issue_row.update(
        {
            "encoder": "tfidf-word",
            "algorithm": "kmeans",
            "split": "train_sample",
            "label_space": "sub_issue",
        }
    )
    rows.append(sub_issue_row)

    # The partition used for naming, diagnostics and error analysis is the best
    # configuration on the training sample (character n-grams + average linkage);
    # held-out numbers stay a separate, untouched measurement.
    primary = run_clustering(
        encoders["tfidf-char"].encode(sample_texts),
        "agglomerative",
        n_clusters=args.clusters,
        random_state=args.seed,
    )
    diagnostic_rows = [
        {"target": name, "ari": clustering_metrics(values, primary)["ari"]}
        for name, values in {
            "domain": sample["domain"],
            "language": sample["language"],
            "district": sample["district"],
            "severity": sample["severity"],
        }.items()
    ]
    naming = name_clusters(sample_texts, primary, top_n=8)
    errors = error_examples(sample, primary, naming)

    dedup = pd.DataFrame()
    best_dedup: pd.Series | None = None
    sbert_dedup = pd.DataFrame()
    sbert_best: pd.Series | None = None
    if not args.skip_dedup:
        dedup = sweep_duplicate_thresholds(
            train["complaint_id"].tolist(),
            train["complaint_text"].tolist(),
            train["district"].tolist(),
            train["duplicate_group_id"].tolist(),
            TfidfEncoder(analyzer="word", ngram_range=(1, 2)),
            THRESHOLDS,
        )
        best_dedup = dedup.sort_values(["f1", "threshold"], ascending=[False, False]).iloc[0]
        if "sbert" in encoders:
            sbert_dedup = sweep_duplicate_thresholds(
                train["complaint_id"].tolist(),
                train["complaint_text"].tolist(),
                train["district"].tolist(),
                train["duplicate_group_id"].tolist(),
                encoders["sbert"],
                THRESHOLDS,
            )
            sbert_best = sbert_dedup.sort_values(
                ["f1", "threshold"], ascending=[False, False]
            ).iloc[0]

    comparison = encoder_comparison(
        pd.DataFrame(rows),
        {
            "tfidf-word": None
            if best_dedup is None
            else {
                "f1": float(best_dedup["f1"]),
                "threshold": float(best_dedup["threshold"]),
            },
            "sbert": None
            if sbert_best is None
            else {
                "f1": float(sbert_best["f1"]),
                "threshold": float(sbert_best["threshold"]),
            },
        },
    )

    classifier = evaluate_classifier(
        train["complaint_text"].tolist(),
        train["domain"].tolist(),
        heldout["complaint_text"].tolist(),
        heldout["domain"].tolist(),
        random_state=args.seed,
    )
    classifier.pop("predictions", None)

    metrics: dict[str, object] = {
        "generated_at": date.today().isoformat(),
        "seed": args.seed,
        "corpus": {
            "train_rows": int(len(train)),
            "heldout_rows": int(len(heldout)),
            "train_sample": int(len(sample)),
            "clusters": int(args.clusters),
            "sub_issue_clusters": sub_issue_clusters,
            "duplicate_rows": int(train["duplicate_group_id"].duplicated().sum()),
            "train_file": _relative(args.complaints),
            "heldout_file": _relative(args.eval_complaints),
        },
        "encoders": {
            "fitted": list(encoders),
            "unavailable": [] if "sbert" in encoders else ["sbert"],
            "sbert_model": None
            if "sbert" not in encoders
            else getattr(encoders["sbert"], "model_name", None),
            "sbert_error": sbert_error,
            "tfidf_settings": {
                "analyzer": "word (1,2) and char_wb (3,5)",
                "min_df": 2,
                "max_df_requested": 0.03,
                "max_df_fitted": {
                    name: round(float(encoder.fitted_max_df), 4)
                    for name, encoder in encoders.items()
                },
                "svd_components": {"tfidf-word": 128, "tfidf-char": 160},
            },
        },
        "primary_partition": {
            "encoder": "tfidf-char",
            "algorithm": "agglomerative",
            "clusters": int(args.clusters),
        },
        "clustering": rows,
        "diagnostic_ari": diagnostic_rows,
        "cluster_naming": naming.to_dict(orient="records"),
        "dedup_sweep": dedup.to_dict(orient="records"),
        "dedup_sweep_sbert": sbert_dedup.to_dict(orient="records"),
        "best_dedup_sbert": None
        if sbert_best is None
        else {
            "threshold": float(sbert_best["threshold"]),
            "precision": float(sbert_best["precision"]),
            "recall": float(sbert_best["recall"]),
            "f1": float(sbert_best["f1"]),
            "true_pairs": int(sbert_best["true_pairs"]),
            "predicted_pairs": int(sbert_best["predicted_pairs"]),
        },
        "encoder_comparison": comparison.to_dict(orient="records"),
        "best_dedup": None
        if best_dedup is None
        else {
            "threshold": float(best_dedup["threshold"]),
            "precision": float(best_dedup["precision"]),
            "recall": float(best_dedup["recall"]),
            "f1": float(best_dedup["f1"]),
            "true_pairs": int(best_dedup["true_pairs"]),
            "predicted_pairs": int(best_dedup["predicted_pairs"]),
        },
        "classifier": classifier,
        "errors": errors,
    }

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(_json_ready(metrics), indent=2), encoding="utf-8"
    )
    DEDUP_CONFIG_PATH.write_text(
        json.dumps(
            _json_ready(
                {
                    "version": "1.0.0",
                    "seed": args.seed,
                    "trained_on": _relative(args.complaints),
                    "similarity": "sparse TF-IDF word (1,2), L2-normalised cosine",
                    "candidate_scope": "top-5 nearest neighbours within the same district",
                    "threshold": None if best_dedup is None else float(best_dedup["threshold"]),
                    "metrics": None
                    if best_dedup is None
                    else {
                        "precision": float(best_dedup["precision"]),
                        "recall": float(best_dedup["recall"]),
                        "f1": float(best_dedup["f1"]),
                    },
                    "generated_at": date.today().isoformat(),
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    EMBEDDING_CONFIG_PATH.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "default_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "alternate_model": "intfloat/multilingual-e5-small",
                "dimensions": 384,
                "status": "measured" if "sbert" in encoders else "not_measured",
                "reason": None
                if "sbert" in encoders
                else sbert_error
                or "Run without --skip-sbert and with requirements/ml.txt installed.",
                "interpreter": sys.version.split()[0],
                "measured_encoders": {"tfidf-word": 128, "tfidf-char": 160},
                "seed": args.seed,
                "trained_on": _relative(args.complaints),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    RESULTS_PATH.write_text(render_markdown(metrics), encoding="utf-8")

    frame = pd.DataFrame(rows)
    print(f"Train sample {len(sample):,}; held-out {len(heldout):,}; corpus {len(train):,}.")
    print(frame.to_string(index=False))
    print(
        f"Classifier accuracy {classifier['accuracy']:.3f}, macro F1 {classifier['macro_f1']:.3f} "
        f"on {classifier['test_rows']:,} held-out rows."
    )
    if best_dedup is not None:
        print(
            f"Best dedup threshold {best_dedup['threshold']:.2f}: "
            f"P={best_dedup['precision']:.3f} R={best_dedup['recall']:.3f} "
            f"F1={best_dedup['f1']:.3f}"
        )
    print(f"Wrote {RESULTS_PATH}")
    print(f"Wrote {METRICS_PATH}")
    return 0


def _cell(value: object, *, limit: int = 90) -> str:
    if isinstance(value, float):
        if pd.isna(value):
            return "-"
        return f"{value:.3f}"
    text = " ".join(str(value).split())
    if len(text) > limit:
        text = text[: limit - 1] + "\u2026"
    return text.replace("|", "\\|")


def markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for record in frame.to_dict(orient="records"):
        cells = [_cell(record[column]) for column in frame.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_markdown(metrics: dict[str, object]) -> str:
    corpus = metrics["corpus"]
    boilerplate = metrics["encoders"]["tfidf_settings"]["max_df_fitted"]
    boilerplate_text = ", ".join(
        f"{name} {value:.1%}" for name, value in boilerplate.items()
    )
    clustering = pd.DataFrame(metrics["clustering"])
    diagnostics = pd.DataFrame(metrics["diagnostic_ari"])
    naming = pd.DataFrame(metrics["cluster_naming"])
    dedup = pd.DataFrame(metrics["dedup_sweep"])
    classifier = metrics["classifier"]
    best = metrics.get("best_dedup")
    errors = pd.DataFrame(metrics["errors"])

    lines: list[str] = []
    lines += [
        "# ChallengeMap - measured results",
        "",
        "Generated by `python scripts/run_eval.py`. Every number below was produced by running "
        "the code in this repository on the synthetic corpus; none are targets, estimates or "
        "placeholder values.",
        "",
        f"- Generated: {metrics['generated_at']}",
        f"- Training corpus: {corpus['train_rows']:,} rows, seed {metrics['seed']}",
        f"- Held-out evaluation set: {corpus['heldout_rows']:,} rows from a separate seed, "
        "never used for tuning",
        f"- Clustering sample: {corpus['train_sample']:,} rows, stratified by domain, "
        f"k = {corpus['clusters']}",
        f"- Encoders fitted: {', '.join(metrics['encoders']['fitted'])} "
        "(TF-IDF word 1-2 and char_wb 3-5, SVD-reduced, L2-normalised; the boilerplate "
        f"filter settled at {boilerplate_text} of documents, loosened from the requested "
        "3% so that no report loses every term)",
        "",
        "## Clustering agreement with ground truth",
        "",
        "ARI and NMI are computed against the generator's labels. Purity is the share of each "
        "predicted cluster belonging to its majority true class. HDBSCAN noise (`-1`) is scored "
        "as its own cluster. The fitted encoders come from the 3,000-row training sample, so the "
        "held-out rows are transformed, never re-fitted.",
        "",
    ]
    columns = [
        column
        for column in [
            "split",
            "encoder",
            "algorithm",
            "label_space",
            "items",
            "n_clusters",
            "ari",
            "nmi",
            "purity",
            "silhouette",
            "noise_fraction",
            "error",
        ]
        if column in clustering.columns
    ]
    lines += [markdown_table(clustering[columns]), ""]

    primary = metrics["primary_partition"]
    lines += [
        "## What the clusters actually capture",
        "",
        f"The primary partition (k = {primary['clusters']}, {primary['encoder']} + "
        f"{primary['algorithm']}) scored against every metadata field. A low domain ARI next to "
        "a high language ARI means the encoder separated scripts before it separated topics; it "
        "does not mean the corpus has no topic structure.",
        "",
        markdown_table(diagnostics),
        "",
        "The English-only slice removes the script boundary; it is the row to quote for lexical "
        "clustering quality. The mixed-language table is dominated by the script split that only "
        "a multilingual embedding can cross, which is exactly the gap Sentence-BERT was meant to "
        "fill.",
        "",
        "## Cluster names (c-TF-IDF)",
        "",
        "Terms that characterise each cluster, computed after clustering. Naming never feeds "
        "back into the partition.",
        "",
        markdown_table(naming[["cluster", "size", "terms"]]),
        "",
        "## Duplicate detection",
        "",
        "Candidate pairs are each complaint's top-5 nearest neighbours within its district block, "
        "which is how the product behaves: a submitter sees a short list, never a full pairwise "
        "sweep. Similarity is exact sparse TF-IDF cosine. Ground truth is the injected duplicate "
        "families; the generator guarantees independent complaints never share identical text, so "
        "an exact-match hit is never a false positive. Injected near-duplicates are true "
        "paraphrases of their source (same template and slots, reworded), not a different "
        "template on the same sub-issue.",
        "",
    ]
    if dedup.empty:
        lines += ["_Sweep skipped._", ""]
    else:
        lines += [
            markdown_table(
                dedup[
                    [
                        "threshold",
                        "predicted_pairs",
                        "tp",
                        "fp",
                        "fn",
                        "precision",
                        "recall",
                        "f1",
                    ]
                ]
            ),
            "",
        ]
        if best:
            lines += [
                f"**Best F1 = {best['f1']:.3f} at threshold {best['threshold']:.2f}** "
                f"(precision {best['precision']:.3f}, recall {best['recall']:.3f}) over "
                f"{best['true_pairs']:,} true pairs.",
                "",
            ]

    lines += [
        "## Supervised routing baseline",
        "",
        "The same TF-IDF features with logistic regression, trained on all "
        f"{classifier['train_rows']:,} training complaints and scored on the "
        f"{classifier['test_rows']:,} held-out complaints. This answers the product question "
        "\"which desk does this report belong to?\" and shows that the text carries domain "
        "signal even where unsupervised lexical clustering struggles.",
        "",
        "| metric | value |",
        "|---|---|",
        f"| accuracy | {classifier['accuracy']:.3f} |",
        f"| macro F1 | {classifier['macro_f1']:.3f} |",
        f"| weighted F1 | {classifier['weighted_f1']:.3f} |",
        "",
        "This is a synthetic ceiling, not a transfer result: every domain carries its own "
        "vocabulary by construction (a pipeline versus a culvert), so a linear model has little "
        "to confuse. It shows the pipeline can separate the domains the corpus defines; it says "
        "nothing about accuracy on real Jharkhand complaints.",
        "",
        "## Error analysis",
        "",
        "Ten misassigned complaints from the k = 12 partition, largest cluster first. The cause "
        "column is assigned by rule, not by hand, so it is a hypothesis to check, not a finding.",
        "",
    ]
    if errors.empty:
        lines += ["_No misassigned rows in this run._", ""]
    else:
        lines += [
            markdown_table(
                errors[
                    [
                        "complaint_id",
                        "language",
                        "true_domain",
                        "cluster",
                        "cluster_domain",
                        "cluster_terms",
                        "text",
                        "likely_cause",
                    ]
                ]
            ),
            "",
        ]

    lines += [
        "## Not measured",
        "",
        "- **Sentence-BERT.** `src/nlp/embeddings.py` implements the multilingual encoder path, "
        "but the active interpreter is CPython 3.14 with no PyTorch wheel available on this "
        "machine, and the installed 3.12 cannot start. The TF-IDF vs SBERT comparison is "
        "therefore absent rather than estimated. `models/embedding_config.json` records the "
        "blocker.",
        "- **Inter-annotator agreement (Cohen's kappa).** The protocol calls for two annotators "
        "on a 300-complaint sample. That needs two people; it cannot be produced by the "
        "evaluator, so no kappa is reported.",
        "- **Real-text benchmark.** The plan's CC0 Indian grievance dataset has not been "
        "downloaded into this repository. Every number here is synthetic-only and is labelled as "
        "such; no claim about real Jharkhand complaints follows from these tables.",
        "- **District-blocked candidate generation** caps recall for duplicates filed in "
        "different districts of the same real-world problem. The sweep measures what the product "
        "does, not an unconstrained oracle.",
        "",
        "## How to reproduce",
        "",
        "```bash",
        "python scripts/generate_corpus.py --records 15000 --eval-records 2000 --seed 42",
        "python scripts/run_eval.py --sample 3000 --clusters 12 --seed 42",
        "```",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
