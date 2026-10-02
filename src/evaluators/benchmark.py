"""Versioned benchmark artifacts and deterministic replay; no model dependencies."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, is_dataclass
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_benchmark(golden, labels):
    golden, labels = Path(golden), Path(labels)
    overlay = json.loads(labels.read_text())
    if overlay['schema_version'] != 1 or overlay['golden_sha256'] != digest(golden):
        raise ValueError('Unsupported labels or golden hash mismatch')
    examples = [json.loads(line) for line in golden.read_text().splitlines() if line.strip()]
    if len(examples) != len(overlay['labels']):
        raise ValueError('Every question must have a label')
    ids = set()
    for example, label in zip(examples, overlay['labels']):
        if label['id'] in ids or label['question_sha256'] != hashlib.sha256(example['question'].encode()).hexdigest():
            raise ValueError('Duplicate ID or question/label mismatch')
        ids.add(label['id'])
        example.update(label)
        example['ground_truth'] = label['reference_answer']
    return examples, overlay


def manifest(root, golden, labels, config, corpus):
    root = Path(root)
    sources = []
    for name, source in sorted(corpus.items()):
        path = root / source['path']
        if digest(path) != source['sha256']:
            raise ValueError(f'Corpus hash mismatch: {name}')
        sources.append({'source': name, **source})
    files = sorted([*root.glob('src/**/*.py'), *root.glob('scripts/*.py')])
    code = {str(p.relative_to(root)): digest(p) for p in files}
    config_json = json.dumps(config, sort_keys=True)
    return {
        'schema_version': 1,
        'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'code_sha256': hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest(),
        'code_files': code,
        'golden_sha256': digest(golden), 'labels_sha256': digest(labels),
        'configuration': config,
        'configuration_sha256': hashlib.sha256(config_json.encode()).hexdigest(),
        'corpus': sources,
    }


def serializable(value):
    if hasattr(value, 'model_dump'):
        return serializable(value.model_dump())
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    return None if isinstance(value, float) and not math.isfinite(value) else value


def evidence_match(required, chunk):
    """Source-version + page + original quote. Legacy/unresolved provenance misses."""
    spans = chunk.get('evidence_spans', [])
    return any(
        span.get('kind', 'original') == 'original'
        and span.get('source_version') == required['source_version']
        and span.get('page_number') == required['page_number']
        and ' '.join(required['quote'].split()) in ' '.join(span.get('text', '').split())
        for span in spans
    )


def score(label, result):
    evidence = label['evidence']
    candidates = result.get('candidates', [])[:20]
    chunks = result.get('chunks', [])
    def recall(items):
        return sum(any(evidence_match(e, c) for c in items) for e in evidence) / len(evidence) if evidence else None
    first = next((rank for rank, c in enumerate(candidates, 1) if any(evidence_match(e, c) for e in evidence)), None)
    metrics = {
        'evidence_recall_at20': recall(candidates),
        'evidence_recall_final': recall(chunks),
        'mrr': (1 / first if first else 0) if evidence else None,
        'complete_evidence': float(recall(chunks) == 1) if evidence else None,
        'outcome_accuracy': float(result['outcome'] == label['expected_outcome']) if result.get('outcome') else None,
    }
    citations = result.get('citations', [])
    invalid = result.get('invalid_citations', [])
    metrics['citation_validity'] = (sum(
        bool(c.get('provenance_status') == 'resolved' and c.get('source_version')
        and c.get('evidence_spans')) for c in citations
    ) / (len(citations) + len(invalid))) if citations or invalid else None
    metrics['citation_support'] = result.get('citation_support')
    # Numeric claims are explicitly annotated with entity/period/scope; plain text
    # number matching would reward wrong-period answers. Missing review is undefined.
    claims = result.get('numeric_claims')
    if label['numeric'] and claims is not None:
        metrics['numeric_accuracy'] = sum(any(
            all(c.get(k) == e[k] for k in ('entity', 'period', 'scope', 'unit'))
            and abs(Decimal(str(c['value'])) - Decimal(e['value'])) <= Decimal(e['tolerance'])
            for c in claims) for e in label['numeric']) / len(label['numeric'])
    else:
        metrics['numeric_accuracy'] = None
    verification = result.get('hallucination')
    unsupported = (verification.get('n_refuted', 0) + verification.get('n_unsupported', 0)) if verification is not None else None
    metrics['unsupported_assertions'] = unsupported
    metrics['outcome_correctness'] = float(result.get('outcome') == label['expected_outcome'] and unsupported == 0) if unsupported is not None and result.get('outcome') else None
    metrics['wrong_period_scope_assertions'] = result.get('wrong_period_scope_assertions')
    for name, value in result.get('metrics', {}).items():
        if name not in metrics:
            metrics[name] = value
    if label['expected_outcome'] in ('refuse', 'clarify'):
        for name in ('answer_relevancy', 'context_precision', 'context_recall'):
            metrics[name] = None
    return metrics


def latency_summary(values):
    values = sorted(v for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    def percentile(q):
        if not values:
            return None
        at = (len(values) - 1) * q
        lo = int(at)
        return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (at - lo)
    return {'p50': percentile(.5), 'p95': percentile(.95), 'denominator': len(values)}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups['all'].append(row)
        groups[row['category']].append(row)
    summary = {}
    for group, items in groups.items():
        values = defaultdict(list)
        for row in items:
            for name, value in row['metrics'].items():
                if isinstance(value, (int, float)) and math.isfinite(value):
                    values[name].append(value)
                else:
                    values[name]  # retain the undefined metric with denominator 0
        summary[group] = {'n_questions': len(items), 'metrics': {
            name: {'mean': sum(v) / len(v) if v else None, 'denominator': len(v)}
            for name, v in values.items()}}
        costs = [r['result'].get('cost_usd') for r in items]
        known = [c for c in costs if isinstance(c, (int, float)) and math.isfinite(c)]
        summary[group]['cost'] = {
            'mean_query_cost_usd': sum(known) / len(items) if len(known) == len(items) else None,
            'priced_query_denominator': len(known), 'unknown_queries': len(items) - len(known),
            'priced_subtotal_usd': sum(known), 'pricing_status': 'configured_estimate',
        }
        summary[group]['latency_ms'] = {
            'end_to_end': latency_summary([r['result'].get('latency_ms') for r in items]),
            'retrieval': latency_summary([r['result'].get('retrieval_latency_ms') for r in items]),
        }
        for scope in ('usage', 'evaluation_usage'):
            receipts = [r['result'].get(scope) for r in items]
            receipts = [r for r in receipts if isinstance(r, dict) and 'events' in r]
            events = [e for receipt in receipts for e in receipt['events']]
            complete = len(receipts) == len(items)
            summary[group][scope] = {'calls': len(events) if receipts else None,
                'receipt_denominator': len(receipts),
                'input_tokens': sum(e['input_tokens'] for e in events) if complete and all(e.get('input_tokens') is not None for e in events) else None,
                'output_tokens': sum(e['output_tokens'] for e in events) if complete and all(e.get('output_tokens') is not None for e in events) else None,
                'reasoning_tokens': sum(e.get('reasoning_tokens') or 0 for e in events) if complete else None,
                'unknown_cost_calls': sum(e.get('cost_usd') is None for e in events),
                'cost_usd': sum(e['cost_usd'] for e in events) if complete and all(e.get('cost_usd') is not None for e in events) else None}
    return summary


def run_benchmark(examples, query_fn, output_dir, run_manifest):
    """Write each result immediately so completed model work survives a later failure."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / 'manifest.json'
    results_path = output_dir / 'results.jsonl'
    if manifest_path.exists() or results_path.exists():
        raise FileExistsError('Use a new run directory; existing results are immutable')
    manifest_path.write_text(json.dumps(run_manifest, indent=2) + '\n')
    rows = []
    with results_path.open('x') as stream:
        for example in examples:
            start = time.perf_counter()
            result = serializable(query_fn(example['question']))
            row = {'id': example['id'], 'question': example['question'],
                   'category': example['category'], 'label': example,
                   'result': result, 'wall_time_seconds': time.perf_counter() - start,
                   'metrics': score(example, result)}
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            rows.append(row)
    summary = summarize(rows)
    (output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def replay(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    for row in rows:
        row['metrics'] = score(row['label'], row['result'])
    return summarize(rows)
