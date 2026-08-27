#!/usr/bin/env python3
"""
Run the offline Ragas evaluation pipeline against the local index.

Kept separate from online querying (scripts/query_cli.py / Streamlit).

Examples:
  # Smoke: first 5 golden questions
  python scripts/run_eval.py --limit 5

  # Full 30-question set
  python scripts/run_eval.py --limit 0 --output tmp_app_ragas.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ragas evaluation offline")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "index")
    parser.add_argument("--cache-root", type=Path, default=ROOT / "cache")
    parser.add_argument(
        "--golden",
        type=Path,
        default=ROOT / "data" / "golden_set" / "golden.jsonl",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max questions (0 = all). Default 5 for cheap iteration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tmp_app_ragas.csv",
        help="CSV path for raw Ragas results",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    from src.services import RAGService

    svc = RAGService(index_dir=args.index_dir, cache_root=args.cache_root)
    if not svc.load_index():
        print(
            f"No index at {args.index_dir}. Run: python scripts/build_index.py",
            file=sys.stderr,
        )
        return 1

    limit = None if args.limit == 0 else args.limit
    print(
        f"Evaluating against {args.golden}"
        + (f" (limit={limit})" if limit else " (full set)")
    )
    result = svc.evaluate(
        args.golden,
        limit=limit,
        verbose=not args.quiet,
        output_csv=args.output,
    )

    summary = {
        "n_examples": result["n_examples"],
        "metrics": result["metrics"],
        "by_category": result["by_category"],
        "cost_usd": result["cost_usd"],
        "wall_time_seconds": result["wall_time_seconds"],
        "output_csv": result["output_csv"],
    }
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nSaved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
