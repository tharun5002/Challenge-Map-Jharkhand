"""Prepare a canonical, validated ChallengeMap complaint CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.complaints import prepare_complaints


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a canonical complaint CSV and write a prepared copy."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="CSV with the canonical complaint columns.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path. Defaults to data/processed/complaints_prepared.csv.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = args.input.resolve()
    output_path = args.output or (
        PROJECT_ROOT / "data" / "processed" / "complaints_prepared.csv"
    )

    try:
        prepared = prepare_complaints(pd.read_csv(source_path))
    except (OSError, pd.errors.ParserError, ValueError) as error:
        print(f"Dataset preparation failed: {error}", file=sys.stderr)
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prepared.to_csv(output_path, index=False)
    except OSError as error:
        print(f"Could not write prepared dataset to {output_path}: {error}", file=sys.stderr)
        return 1

    print(f"Prepared {len(prepared):,} records from validated input.")
    print(f"Synthetic records: {int(prepared['source_type'].eq('synthetic').sum()):,}")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
