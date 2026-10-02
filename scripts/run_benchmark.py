#!/usr/bin/env python3
"""Capture a bounded benchmark, or replay saved results without model calls."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.evaluators.benchmark import load_benchmark, manifest, replay, run_benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--index-dir', type=Path, default=ROOT / 'index')
    parser.add_argument('--golden', type=Path, default=ROOT / 'data/golden_set/golden.jsonl')
    parser.add_argument('--labels', type=Path, default=ROOT / 'data/golden_set/labels.v1.json')
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(args.replay), indent=2))
        return
    if not args.output_dir or args.limit < 0:
        parser.error('Capture requires --output-dir and a nonnegative --limit (0 = all)')
    examples, overlay = load_benchmark(args.golden, args.labels)
    from src.core.config import settings
    from src.services import RAGService
    svc = RAGService(index_dir=args.index_dir)
    if not svc.load_index():
        parser.error('No saved index; build explicitly before benchmarking')
    config = {'arm': 'A', 'models': {'generator': settings.llm_model, 'judge': settings.judge_model,
              'embedding': settings.embedding_model}, 'index': json.loads(svc.meta_path.read_text()),
              'index_artifacts': {p.name: __import__('hashlib').sha256(p.read_bytes()).hexdigest()
                                  for p in (svc.meta_path, svc.parents_path, svc.children_path)},
              'quick_k': 3, 'deep_k': 8, 'fetch_k': 20, 'rrf_k': 60,
              'evidence_policy': 'actual_quick_deep', 'limit': args.limit}
    run_manifest = manifest(ROOT, args.golden, args.labels, config, overlay['corpus'])
    selected = examples[:args.limit] if args.limit else examples
    def query(question):
        return asdict(svc.query(question))
    print(json.dumps(run_benchmark(selected, query, args.output_dir, run_manifest), indent=2))


if __name__ == '__main__':
    main()
