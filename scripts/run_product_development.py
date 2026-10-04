"""Capture only the frozen authentic development cases; never opens a holdout."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / 'docs/fixtures/product/development_cases.v1.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_cases(path=FIXTURE):
    labels = json.loads(path.read_text())
    cases = labels['cases']
    slices = Counter(c['primary_slice'] for c in cases)
    if (labels['split'] != 'development' or len(cases) != 48 or len(slices) != 6
            or set(slices.values()) != {8} or len({c['case_id'] for c in cases}) != 48):
        raise ValueError('Development cases must have 48 unique IDs and six eight-case slices')
    for tag, minimum in [('numeric', 20), ('narrative', 8), ('answerable_cross_company', 8)]:
        if sum(tag in c['tags'] for c in cases) < minimum:
            raise ValueError(f'Development coverage is incomplete: {tag}')
    for filename, expected in labels['artifact_sha256'].items():
        if Path(filename).name != filename or digest(path.parent / filename) != expected:
            raise ValueError('Frozen development source/card manifest has changed')
    from src.financial.research import ResearchRequest
    from src.financial.evidence import EvidenceSearchRequest
    for case in cases:
        if case['lane'] == 'research':
            ResearchRequest.model_validate(case['request'])
        elif case['lane'] == 'narrative':
            EvidenceSearchRequest.model_validate(case['request'])
        elif case['lane'] != 'question':
            raise ValueError('Unknown development lane')
    return labels


def assess(case, result):
    """Mechanical checks only. Exact quotes do not certify semantic support."""
    expected = case['expected']
    checks = {'expected_outcome': result['outcome'] == expected['outcome'],
              'planner_disabled': result['usage'].get('planner_calls') == 0,
              'generator_ceiling': result['usage'].get('generator_calls', 0) <= (1 if case['lane'] == 'narrative' else 0),
              'original_budget': result.get('original_tokens', 0) <= 6000}
    if expected['observations']:
        supported = {i for cell in result.get('coverage', []) if cell['status'] == 'supported'
                     for i in cell['observation_ids']}
        actual = {o['observation_id']: o for o in result.get('observations', [])}
        checks['numeric_original_bindings'] = all(
            label['observation_id'] in supported and label['observation_id'] in actual
            and all(actual[label['observation_id']].get(k) == v for k,v in label.items())
            for label in expected['observations'])
    checks['calculations'] = [{k:r[k] for k in ('operation', 'displayed_result')}
                              for r in result.get('calculations', [])] == expected['calculations']
    if case['lane'] == 'narrative':
        passages = {p['evidence_id']: p for p in result.get('passages', [])}
        checks['quoted_original_provenance'] = all(
            c['evidence_id'] in passages and c['source'] == passages[c['evidence_id']]['source']
            and passages[c['evidence_id']]['text'][c['char_start']:c['char_end']] == c['quote']
            and c['task_id'] == passages[c['evidence_id']]['task_id']
            and c['review_status'] == 'unreviewed_generated_claim' for c in result.get('claims', []))
        checks['no_self_certification'] = result['synthesis_review_status'] in ('unreviewed', 'withheld')
    return checks


def summarize(rows):
    groups = {}
    for name in sorted({r['primary_slice'] for r in rows}):
        group = [r for r in rows if r['primary_slice'] == name]
        groups[name] = {'mechanical_pass': sum(all(r['checks'].values()) for r in group), 'denominator': len(group)}
    events = [e for r in rows for e in r['result']['usage'].get('events', [])]
    latencies = sorted(r['latency_seconds'] for r in rows)
    known = all(e['cost_usd'] is not None for e in events)
    return {'status': 'development_capture_release_held', 'case_count': len(rows), 'slices': groups,
            'mechanical_pass': sum(all(r['checks'].values()) for r in rows),
            'numeric_bindings': {'passed': sum(r['checks'].get('numeric_original_bindings', False) for r in rows),
                                 'denominator': sum('numeric_original_bindings' in r['checks'] for r in rows)},
            'semantic_citation_support': {'value': None, 'reviewed_denominator': 0},
            'strict_authentic_accuracy': {'value': None, 'reviewed_denominator': 0},
            'planner_calls': sum(r['result']['usage'].get('planner_calls', 0) for r in rows),
            'generation_calls': sum(r['result']['usage'].get('generator_calls', 0) for r in rows),
            'input_tokens': sum(e['input_tokens'] or 0 for e in events),
            'output_tokens': sum(e['output_tokens'] or 0 for e in events),
            'configured_estimate_usd': sum(e['cost_usd'] for e in events) if known else None,
            'unpriced_events': sum(e['cost_usd'] is None for e in events),
            'latency_seconds': {'p50': statistics.median(latencies),
                                'p95': latencies[min(len(latencies)-1, int(.95*(len(latencies)-1)))]},
            'saved_history_reopens': sum(r['history_reopen_equal'] for r in rows),
            'holdout': 'not_accessed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--pricing', type=Path, required=True)
    parser.add_argument('--capture', action='store_true', help='Without this flag, validate frozen labels only')
    args = parser.parse_args()
    labels = frozen_cases()
    if not args.capture:
        print(json.dumps({'label_sha256': digest(FIXTURE), 'cases': 48, 'coverage': labels['coverage'],
                          'numeric_cases': labels['numeric_cases'], 'holdout': 'not_accessed'}, indent=2))
        return
    from src.core.config import settings
    prices = json.loads(args.pricing.read_text())
    if settings.llm_model not in prices:
        raise ValueError('Capture model has no frozen price')
    from dotenv import dotenv_values
    from src.services.persistent_service import PersistentRAGService
    from src.storage.objects import LocalObjects
    profile = dotenv_values(ROOT / 'index/product-local/runtime.env')
    service = PersistentRAGService(profile['DATABASE_URL'], owner=profile['FINRAG_OWNER'],
        objects=LocalObjects(profile['FINRAG_OBJECT_DIR']), index_dir=ROOT/'index/product-local')
    service.cost_tracker.pricing = prices
    receipts = {r['report_id']: r for r in json.loads((FIXTURE.parent/'ingestion_receipts.v1.json').read_text())['reports']}
    # Check ALL authorized source versions/builds/hashes before the first paid call.
    for case in labels['cases']:
        snap = service.registry.research_snapshot(service.owner, case['request']['selections'], include_blocks=False)
        expected = {(receipts[r]['source_id'],receipts[r]['version_id'],receipts[r]['build_id'],receipts[r]['source_sha256'])
                    for r in case['report_ids']}
        actual = {(p.source_id,p.version_id,p.build_id,p.source_hash) for p in snap['sources']}
        if actual != expected:
            raise ValueError('Live authorized source set differs from frozen development manifest')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    code_files = [*sorted((ROOT/'src/financial').glob('*.py')), ROOT/'src/services/persistent_service.py', Path(__file__)]
    manifest = {'split': 'development', 'label_sha256': digest(FIXTURE), 'pricing_sha256': digest(args.pricing),
        'pricing': prices, 'model': settings.llm_model, 'reasoning_effort': os.getenv('REASONING_EFFORT'),
        'code_sha256': {str(p.relative_to(ROOT)): digest(p) for p in code_files},
        'source_artifact_sha256': labels['artifact_sha256'], 'holdout': 'not_accessed',
        'api_policy': 'one synthesis call per narrative; no retries, planner, VLM, embedding or judge calls',
        'cost_policy': 'Configured base input/output price estimate; raw provider usage retained. Not an invoice.'}
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    rows = []
    with (args.output_dir/'results.jsonl').open('x') as output:
        for case in labels['cases']:
            started = time.monotonic()
            if case['lane'] == 'question':
                result = service.research_question(**case['request'], save=True)
            else:
                execute = service.research_evidence if case['lane'] == 'narrative' else service.research
                result = execute(case['request'], save=True)
            elapsed = time.monotonic()-started
            reopened = service.registry.research_run(service.owner, result['run_id'])['payload']
            checks = assess(case, result)
            row = {'case_id': case['case_id'], 'primary_slice': case['primary_slice'], 'tags': case['tags'],
                   'latency_seconds': elapsed, 'history_reopen_equal': reopened == result, 'checks': checks, 'result': result}
            checks['history_reopen_equal'] = row['history_reopen_equal']
            rows.append(row)
            output.write(json.dumps(row, ensure_ascii=False)+'\n'); output.flush()
            print(f"{case['case_id']}: {result['outcome']} / {'pass' if all(checks.values()) else 'CHECK'} / {elapsed:.2f}s", flush=True)
    summary = summarize(rows)
    (args.output_dir/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
