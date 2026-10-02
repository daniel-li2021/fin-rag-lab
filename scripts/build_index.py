#!/usr/bin/env python3
"""
Build (or rebuild) the parent-child hybrid index from PDFs.

Examples:
  # Default uploads (wells_fargo, tesla, amd if present)
  python scripts/build_index.py

  # Explicit files
  python scripts/build_index.py --inputs data/uploads/wells_fargo.pdf data/uploads/tesla.pdf

  # First 5 pages only (cheap smoke test)
  python scripts/build_index.py --max-pages 5
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


def _default_inputs(upload_dir: Path) -> list[Path]:
    preferred = ["wells_fargo.pdf", "tesla.pdf", "amd.pdf"]
    found = [upload_dir / n for n in preferred if (upload_dir / n).exists()]
    if found:
        return found
    return sorted(upload_dir.glob("*.pdf"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Fin-RAG parent-child index")
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        help="PDF paths (default: data/uploads/{wells_fargo,tesla,amd}.pdf)",
    )
    parser.add_argument("--index-dir", type=Path, default=ROOT / "index")
    parser.add_argument("--cache-root", type=Path, default=ROOT / "cache")
    parser.add_argument("--upload-dir", type=Path, default=ROOT / "data" / "uploads")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--parent-size", type=int, default=800)
    parser.add_argument("--child-size", type=int, default=150)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    inputs = args.inputs or _default_inputs(args.upload_dir)
    if not inputs:
        print(f"No PDFs found under {args.upload_dir}", file=sys.stderr)
        return 1

    from src.services import RAGService

    svc = RAGService(
        index_dir=args.index_dir,
        cache_root=args.cache_root,
        upload_dir=args.upload_dir,
        parent_size=args.parent_size,
        child_size=args.child_size,
    )

    print(f"Building index from {len(inputs)} PDF(s) → {args.index_dir}")
    try:
        result = svc.ingest_and_index(
            inputs,
            max_pages=args.max_pages,
            reset=True,
            verbose=not args.quiet,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in result.items() if k != "documents"}, indent=2))
    for doc in result["documents"]:
        print(
            f"  - {doc['title']}: {doc['n_children']} children / "
            f"{doc['n_parents']} parents (cache_hit={doc['cache_hit']})"
        )
    cost = "unknown" if result["cost_usd"] is None else f"${result['cost_usd']:.4f}"
    print(f"\nDone. Cost: {cost}  time: {result['wall_time_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
