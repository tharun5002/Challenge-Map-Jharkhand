"""Run Sentence-BERT + K-Means on a validated canonical complaint CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.complaints import prepare_complaints
from src.nlp.embeddings import DEFAULT_MULTILINGUAL_MODEL, load_sentence_encoder
from src.nlp.topic_discovery import discover_sentence_topics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover complaint groups using multilingual sentence embeddings "
            "and K-Means."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Validated canonical complaint CSV.",
    )
    parser.add_argument(
        "--assignments",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "topic_assignments.csv",
        help="Output CSV for per-complaint topic assignments.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "topic_summary.csv",
        help="Output CSV for topic sizes and representative complaints.",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=5,
        help="Requested number of K-Means groups (default: 5).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MULTILINGUAL_MODEL,
        help="Sentence Transformers model name or local model path.",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda", "auto"),
        default="cpu",
        help="Inference device (default: cpu).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding batch size (default: 32).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = pd.read_csv(args.input)
        complaints = prepare_complaints(raw)
        encoder = load_sentence_encoder(args.model, args.device)
        assignments, summary, metrics = discover_sentence_topics(
            complaints["complaint_text"].tolist(),
            encoder,
            args.clusters,
            batch_size=args.batch_size,
        )
        assignments.insert(0, "complaint_id", complaints["complaint_id"])
        assignments.insert(1, "district", complaints["district"])

        args.assignments.parent.mkdir(parents=True, exist_ok=True)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        assignments.to_csv(args.assignments, index=False)
        summary.to_csv(args.summary, index=False)
    except (
        OSError,
        ValueError,
        RuntimeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as error:
        print(f"Topic discovery failed: {error}", file=sys.stderr)
        return 1

    print(f"Complaints analyzed: {len(assignments):,}")
    print(f"Topics produced: {len(summary):,}")
    for metric, value in metrics.items():
        rendered = "not available" if value is None else f"{value:.4f}"
        print(f"{metric}: {rendered}")
    print(f"Assignments: {args.assignments}")
    print(f"Topic summary: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
