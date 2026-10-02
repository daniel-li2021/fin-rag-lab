#!/usr/bin/env python3
"""
Query the local Fin-RAG index from the command line.

Examples:
  python scripts/query_cli.py "What was Wells Fargo's Q4 2025 net income?"
  python scripts/query_cli.py --verify "What was Tesla's vehicle production?"
  python scripts/query_cli.py --interactive
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


def _print_result(result, *, show_chunks: bool = False) -> None:
    print("\n" + "=" * 60)
    print(f"Q: {result.query}")
    print("-" * 60)
    print(result.answer)
    print("-" * 60)
    cost = "unknown" if result.cost_usd is None else f"${result.cost_usd:.4f}"
    print(
        f"type={result.query_type}  refused={result.refused}  "
        f"latency={result.latency_ms:.0f}ms  chunks={result.n_chunks_retrieved}  "
        f"cost={cost}  outcome={result.outcome}"
    )
    print(f"stages: {' → '.join(result.stages)}")
    if result.citations:
        print("\nCitations:")
        for i, c in enumerate(result.citations, start=1):
            page = c.get("page_number")
            page_s = f"p.{page}" if page else "p.?"
            print(f"  [{c.get('source_number') or i}] {page_s}  {c.get('text_preview', '')[:120]}")
    if result.hallucination:
        h = result.hallucination
        print(
            f"\nHallucination check: faith={h.get('faithfulness_score', 0):.0%}  "
            f"entailed={h.get('n_entailed')} unsupported={h.get('n_unsupported')} "
            f"refuted={h.get('n_refuted')}"
        )
        for claim in h.get("claims", []):
            print(f"  [{claim['verdict'].upper():12s}] {claim['claim']}")
    if show_chunks:
        print("\nRetrieved chunks:")
        for i, chunk in enumerate(result.chunks, start=1):
            print(f"  --- chunk {i} (page {chunk.page_number}) ---")
            print(f"  {chunk.text[:400]}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Fin-RAG index")
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "index")
    parser.add_argument("--cache-root", type=Path, default=ROOT / "cache")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run optional HallucinationDetector after answering",
    )
    parser.add_argument("--show-chunks", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="REPL mode"
    )
    args = parser.parse_args()

    from src.services import RAGService

    svc = RAGService(index_dir=args.index_dir, cache_root=args.cache_root)
    if not svc.load_index():
        print(
            f"No index at {args.index_dir}. Run: python scripts/build_index.py",
            file=sys.stderr,
        )
        return 1

    status = svc.status()
    if not args.json:
        print(
            f"Index ready: {status.n_documents} docs, "
            f"{status.n_children} children, {status.n_parents} parents"
        )

    def run_one(q: str) -> None:
        result = svc.query(q, verify_hallucination=args.verify)
        if args.json:
            payload = result.to_display_dict()
            print(json.dumps(payload, indent=2, default=str))
        else:
            _print_result(result, show_chunks=args.show_chunks)

    if args.interactive:
        print("Interactive mode — empty line or Ctrl-D to exit.")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not q:
                break
            run_one(q)
        return 0

    if not args.question:
        parser.error("question required (or use --interactive)")

    run_one(args.question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
