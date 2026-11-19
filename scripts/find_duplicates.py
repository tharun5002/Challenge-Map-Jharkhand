"""Find semantic complaint-pair candidates in a canonical CSV dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.complaints import prepare_complaints
from src.nlp.duplicate_detection import detect_duplicate_candidates
from src.nlp.embeddings import DEFAULT_MULTILINGUAL_MODEL, load_sentence_encoder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find semantically similar complaint pairs for human review; "
            "pairs are not automatically classified as duplicates."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Canonical complaint CSV with unique IDs, text, and district.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "duplicate_candidates.csv",
        help="Output CSV for candidate pairs.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum cosine similarity from 0 to 1 (default: 0.85).",
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
        complaints = prepare_complaints(pd.read_csv(args.input))
        encoder = load_sentence_encoder(args.model, args.device)
        candidates = detect_duplicate_candidates(
            complaints["complaint_id"].tolist(),
            complaints["complaint_text"].tolist(),
            encoder,
            similarity_threshold=args.threshold,
            batch_size=args.batch_size,
        )
        district_lookup = complaints.set_index("complaint_id")["district"]
        date_lookup = complaints.set_index("complaint_id")["complaint_date"]
        if not candidates.empty:
            candidates.insert(
                2,
                "district",
                candidates["complaint_id"].map(district_lookup),
            )
            candidates.insert(
                3,
                "similar_district",
                candidates["similar_complaint_id"].map(district_lookup),
            )
            candidates.insert(
                4,
                "complaint_date",
                candidates["complaint_id"].map(date_lookup),
            )
            candidates.insert(
                5,
                "similar_complaint_date",
                candidates["similar_complaint_id"].map(date_lookup),
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        candidates.to_csv(args.output, index=False)
    except (
        OSError,
        ValueError,
        RuntimeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as error:
        print(f"Duplicate candidate search failed: {error}", file=sys.stderr)
        return 1

    print(f"Complaints analyzed: {len(complaints):,}")
    print(f"Candidate pairs for human review: {len(candidates):,}")
    print(f"Similarity threshold: {args.threshold:.2f}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
