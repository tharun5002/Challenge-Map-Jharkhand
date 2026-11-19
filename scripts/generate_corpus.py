"""Generate the seeded synthetic corpus and its provenance manifest."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.synthetic_generator import manifest_rows, write_corpus

MANIFEST = PROJECT_ROOT / "data" / "source_manifest.csv"
MANIFEST_COLUMNS = [
    "dataset_file",
    "publisher",
    "source_url",
    "license_or_consent_basis",
    "acquired_at",
    "records_imported",
    "transformations",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=15_000)
    parser.add_argument("--eval-records", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "synthetic",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = write_corpus(
            args.out_dir,
            n_records=args.records,
            n_eval=args.eval_records,
            seed=args.seed,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Corpus generation failed: {error}", file=sys.stderr)
        return 1

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in manifest_rows(summary):
            writer.writerow(row)

    print(f"Generated {summary['records']:,} complaints (seed {summary['seed']}).")
    print(f"Evaluation set: {summary['eval_records']:,} held-out complaints.")
    print(
        f"Districts: {summary['districts']}/24 | domains: {summary['domains']} | "
        f"sub-issues: {summary['sub_issues']}"
    )
    print(
        f"Injected duplicates: {summary['duplicates']:,} inside "
        f"{summary['duplicate_groups']:,} report families"
    )
    print("Languages: " + ", ".join(f"{k}={v:,}" for k, v in summary["languages"].items()))
    for key, path in summary["paths"].items():
        print(f"  {key:16} {path}")
    print(f"Manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
