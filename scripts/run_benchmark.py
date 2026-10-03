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
    parser.add_argument('--backend', choices=('chroma', 'postgres'), default='chroma')
    parser.add_argument('--owner', default='default', help='Authorized Postgres source owner')
    parser.add_argument('--pricing', type=Path, help='Frozen per-1K-token pricing JSON')
    parser.add_argument('--golden', type=Path, default=ROOT / 'data/golden_set/golden.jsonl')
    parser.add_argument('--labels', type=Path, default=ROOT / 'data/golden_set/labels.v1.json')
    parser.add_argument('--verify', action='store_true', help='Verify assertions, including refusal prose')
    parser.add_argument('--ragas', action='store_true', help='Add paid secondary judging on supported labels')
    parser.add_argument('--judge-embedding-model', default='text-embedding-3-small')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--ids', nargs='+', help='Run only these stable benchmark IDs')
    parser.add_argument('--supplement-k', type=int, choices=range(9), default=0,
                        help='Opt-in bounded original-parent evidence supplements (0–8)')
    parser.add_argument('--reuse-query-embeddings', action='store_true',
                        help='Reuse verified same-model text embeddings for identical queries')
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(args.replay), indent=2))
        return
    if not args.output_dir or args.limit < 0:
        parser.error('Capture requires --output-dir and a nonnegative --limit (0 = all)')
    examples, overlay = load_benchmark(args.golden, args.labels)
    from src.core.config import settings
    from src.observability import CostTracker
    tracker = CostTracker(pricing=json.loads(args.pricing.read_text())) if args.pricing else CostTracker()
    if args.backend == 'postgres':
        from src.services.persistent_service import PersistentRAGService
        svc = PersistentRAGService(os.environ['DATABASE_URL'], owner=args.owner,
                                   index_dir=args.index_dir, cost_tracker=tracker)
    else:
        from src.services import RAGService
        svc = RAGService(index_dir=args.index_dir, cost_tracker=tracker)
    if not svc.load_index():
        parser.error('No saved index; build explicitly before benchmarking')
    if args.reuse_query_embeddings:
        if args.backend != 'postgres':
            parser.error('Query embedding reuse currently requires the retained Postgres backend')
        svc.embeddings.query_embedding_store = svc.embeddings.document_embedding_store
    if args.backend == 'postgres':
        with svc.registry.connect() as db:
            builds = db.execute('''SELECT s.source_id,s.title,v.sha256,b.build_id,b.manifest
                FROM sources s JOIN source_versions v ON v.version_id=s.active_version_id
                JOIN retrieval_builds b ON b.build_id=s.active_build_id
                WHERE s.owner_id=%s AND s.status<>'archived' ORDER BY s.source_id''', (args.owner,)).fetchall()
            if sorted(b['sha256'] for b in builds) != sorted(s['sha256'] for s in overlay['corpus'].values()):
                parser.error('Authorized active corpus differs from the golden corpus')
            if any(b['manifest'].get('evidence_revision') != 1 for b in builds):
                parser.error('Active builds lack corrected provenance')
            from src.evaluators.benchmark import serializable
            meta = serializable({**svc.manifest(), 'builds': [
                {**b, 'source_id': str(b['source_id']), 'build_id': str(b['build_id'])} for b in builds]})
            artifacts = db.execute('''SELECT c.build_id,c.chunk_id,c.payload,e.model,e.input_hash,e.embedding::text
                FROM chunks c LEFT JOIN chunk_embeddings e USING(build_id,chunk_id)
                WHERE c.build_id=ANY(%s) ORDER BY c.build_id,c.ordinal''', ([b['build_id'] for b in builds],)).fetchall()
            artifact_hashes = {'postgres_chunks_vectors': hashlib.sha256(
                json.dumps(artifacts, sort_keys=True, default=str).encode()).hexdigest()}
    else:
        meta = json.loads(svc.meta_path.read_text())
        if meta.get('evidence_revision') != 1:
            parser.error('Saved index lacks corrected provenance; rebuild explicitly from verified caches before a new benchmark')
        if meta.get('embedding_model') != svc.vector.embedding_model:
            parser.error('Runtime embedding model differs from the saved build')
        artifact_paths = [svc.meta_path, svc.parents_path, svc.children_path, *sorted(p for p in svc.chroma_dir.rglob('*') if p.is_file())]
        artifact_hashes = {str(p.relative_to(svc.index_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_paths}
    dependencies = [line.split('==')[0] for line in (ROOT / 'requirements.txt').read_text().splitlines() if '==' in line]
    config = {'arm': 'A', 'models': {'generator': settings.llm_model, 'judge': settings.judge_model if args.ragas or args.verify else None,
              'embedding': settings.embedding_model}, 'index': meta, 'backend': args.backend, 'owner': args.owner,
              'index_artifacts': artifact_hashes,
              'dependencies': {name: version(name) for name in [*dependencies, 'openai', 'httpx']},
              'quick_k': 3, 'deep_k': 8, 'fetch_k': 20, 'rrf_k': 60,
              'supplement_k': args.supplement_k,
              'query_embedding_cache': args.reuse_query_embeddings,
              'question_ids': args.ids,
              'evidence_policy': 'actual_quick_deep', 'limit': args.limit,
              'verify_hallucination': args.verify, 'ragas_enabled': args.ragas,
              'judge_embedding_model': args.judge_embedding_model if args.ragas else None,
              'reasoning_effort': os.getenv('REASONING_EFFORT'),
              'pricing_snapshot': svc.cost_tracker.report()['pricing_snapshot'],
              'requirements_sha256': hashlib.sha256((ROOT / 'requirements.txt').read_bytes()).hexdigest()}
    run_manifest = manifest(ROOT, args.golden, args.labels, config, overlay['corpus'])
    if args.ids:
        if set(args.ids) - {example['id'] for example in examples}:
            parser.error('Unknown benchmark ID')
        examples = [example for example in examples if example['id'] in args.ids]
    selected = examples[:args.limit] if args.limit else examples
    def query(question):
        result = asdict(svc.query(question, verify_hallucination=args.verify, supplement_k=args.supplement_k))
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
