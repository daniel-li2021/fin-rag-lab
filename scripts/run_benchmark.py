#!/usr/bin/env python3
"""Capture a bounded benchmark, or replay saved results without model calls."""
import argparse
from dataclasses import asdict
from importlib.metadata import version
import hashlib
import json
import os
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
    parser.add_argument('--verify', action='store_true', help='Verify assertions, including refusal prose')
    parser.add_argument('--ragas', action='store_true', help='Add paid secondary judging on supported labels')
    parser.add_argument('--judge-embedding-model', default='text-embedding-3-small')
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
    meta = json.loads(svc.meta_path.read_text())
    if meta.get('evidence_revision') != 1:
        parser.error('Saved index lacks corrected provenance; rebuild explicitly from verified caches before a new benchmark')
    if meta.get('embedding_model') != svc.vector.embedding_model:
        parser.error('Runtime embedding model differs from the saved build')
    artifact_paths = [svc.meta_path, svc.parents_path, svc.children_path, *sorted(p for p in svc.chroma_dir.rglob('*') if p.is_file())]
    dependencies = [line.split('==')[0] for line in (ROOT / 'requirements.txt').read_text().splitlines() if '==' in line]
    config = {'arm': 'A', 'models': {'generator': settings.llm_model, 'judge': settings.judge_model if args.ragas or args.verify else None,
              'embedding': settings.embedding_model}, 'index': json.loads(svc.meta_path.read_text()),
              'index_artifacts': {str(p.relative_to(svc.index_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_paths},
              'dependencies': {name: version(name) for name in [*dependencies, 'openai', 'httpx']},
              'quick_k': 3, 'deep_k': 8, 'fetch_k': 20, 'rrf_k': 60,
              'evidence_policy': 'actual_quick_deep', 'limit': args.limit,
              'verify_hallucination': args.verify, 'ragas_enabled': args.ragas,
              'judge_embedding_model': args.judge_embedding_model if args.ragas else None,
              'reasoning_effort': os.getenv('REASONING_EFFORT'),
              'pricing_snapshot': svc.cost_tracker.report()['pricing_snapshot'],
              'requirements_sha256': hashlib.sha256((ROOT / 'requirements.txt').read_bytes()).hexdigest()}
    run_manifest = manifest(ROOT, args.golden, args.labels, config, overlay['corpus'])
    selected = examples[:args.limit] if args.limit else examples
    def query(question):
        result = asdict(svc.query(question, verify_hallucination=args.verify))
        if args.ragas:
            from src.evaluators import RagasEvaluator
            from src.evaluators.benchmark import serializable
            example = next(e for e in selected if e['question'] == question)
            with svc.cost_tracker.request() as judge_receipt:
                evaluator = RagasEvaluator(cost_tracker=svc.cost_tracker, embedding_model=args.judge_embedding_model)
                df = evaluator.evaluate(lambda _: result, [example], verbose=False)
            result['evaluation_usage'] = judge_receipt.report()
            result['metrics'] = serializable({name: float(df[name].iloc[0]) for name in evaluator.metric_names})
        return result
    print(json.dumps(run_benchmark(selected, query, args.output_dir, run_manifest), indent=2))


if __name__ == '__main__':
    main()
