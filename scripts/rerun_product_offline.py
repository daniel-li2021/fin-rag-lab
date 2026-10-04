"""Re-execute deterministic development paths; replay unchanged narrative claims.

No provider calls. This is a domain/registry regression, not fresh generation or
an HTTP/UI benchmark. Search must reproduce the pinned original passages before
a previously generated narrative can be reused.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.financial.evidence import EvidenceSearchRequest, search_evidence
from src.financial.intent import parse_question, question_filters, resolve_question
from src.financial.models import FinancialObservation
from src.financial.presentation import narrative_answer
from src.financial.narrative import original_excerpts, synthesize_evidence
from src.observability import CostTracker
from src.financial.research import ResearchRequest, _canonical, run_research
from src.storage.registry import Registry
from scripts.run_product_development import assess, frozen_cases, summarize
from scripts.replay_product_review import digest


def execute(case, registry, owner):
    request = case['request']
    snapshot = registry.research_snapshot(owner, request['selections'], include_blocks=False)
    if case['lane'] == 'question':
        parsed = parse_question(request['question'], snapshot['inventory'])
        observations = [] if 'outcome' in parsed else registry.observations(
            owner, [p.build_id for p in snapshot['sources']], question_filters(parsed))
        resolution = resolve_question(request['question'], request['selections'], snapshot['inventory'],
            [FinancialObservation.model_validate(o) for o in observations], parsed)
        if 'request' not in resolution:
            return {**resolution, 'contract_version': 'research-question-v1', 'request': request,
                    'manifest': [p.model_dump(mode='json') for p in snapshot['sources']],
                    'inventory': snapshot['inventory'], 'calculations': [], 'calculation_gaps': []}
        request = resolution['request']
        for calculation in request['calculations']:
            calculation['period_policy'] = case['request'].get('period_policy', 'exact_duration')
    plan = ResearchRequest.model_validate(request)
    filters = []
    for task in plan.tasks:
        period = task.period.model_dump(mode='json')
        if task.period.calendar != 'unresolved':
            period.pop('fiscal_label')
        filters.append({'company_id': task.company_id, 'metric_id': task.metric_id,
                        'scope': task.scope, 'basis': task.basis, 'period': period})
    stored = registry.observations(owner, [p.build_id for p in snapshot['sources']], filters,
                                   [o.observation_id for o in plan.observations])
    observations = {o['observation_id']: o for o in stored}
    for observation in plan.observations:
        previous = observations.get(observation.observation_id)
        if previous and previous != observation.model_dump(mode='json'):
            raise ValueError('Request conflicts with immutable stored observation')
        observations[observation.observation_id] = observation.model_dump(mode='json')
    plan = ResearchRequest.model_validate({**plan.model_dump(mode='json'), 'observations': list(observations.values())})
    snapshot['blocks'] = registry.observation_blocks(owner, snapshot['sources'], plan.observations)
    return run_research(plan, snapshot)


def replay_narrative(case, previous, registry, owner, *, presentation=False):
    request = EvidenceSearchRequest.model_validate(case['request'])
    snapshot = registry.research_snapshot(owner, case['request']['selections'])
    searched = search_evidence(request, snapshot)
    if searched['passages'] != previous['passages'] or searched['coverage'] != previous['coverage']:
        raise ValueError('Changed original search requires a new narrative capture/review')
    # Revalidate the saved draft through the integrated synthesis path. This adapter
    # returns saved text only; it cannot construct a provider client or make a call.
    from types import SimpleNamespace
    excerpts = original_excerpts({p['evidence_id']: p for p in searched['passages']})
    draft = []
    for claim in previous['claims']:
        excerpt = next(e for e in excerpts.values() if all(e[k] == claim[k]
                       for k in ('task_id', 'evidence_id', 'quote', 'char_start', 'char_end')))
        draft.append({'task_id': claim['task_id'], 'excerpt_id': excerpt['excerpt_id'], 'text': claim['text']})
    class SavedDraft:
        def invoke(self, messages):
            return SimpleNamespace(content=json.dumps({'claims': draft}), response_metadata={})
    integrated = synthesize_evidence(searched, CostTracker(), llm=SavedDraft(), model='saved-draft-replay')
    if integrated['claims'] != previous['claims'] or integrated['outcome'] != previous['outcome']:
        raise ValueError('Saved draft changed during integrated synthesis validation')
    result = {**integrated,
              'archived_generation_usage': previous['usage'],
              'usage': searched['usage'],
              'generation_provenance': 'saved draft revalidated through integrated synthesis; no provider call'}
    result.pop('synthesis_latency_seconds', None)
    if presentation and previous['claims']:
        result['answer'] = narrative_answer({t['task_id']: t for t in case['request']['tasks']}, previous['claims'])
    return result


def capture(labels, output, *, previous=None, presentation=False):
    from dotenv import dotenv_values
    profile = dotenv_values(ROOT / 'index/product-local/runtime.env')
    registry, owner = Registry(profile['DATABASE_URL']), profile['FINRAG_OWNER']
    receipts = json.loads((ROOT / 'docs/fixtures/product/ingestion_receipts.v1.json').read_text())['reports']
    base = Path(profile['FINRAG_OBJECT_DIR']) / hashlib.sha256(owner.encode()).hexdigest()
    for receipt in receipts:
        if digest(base / receipt['source_sha256']) != receipt['source_sha256']:
            raise ValueError('Original byte hash mismatch')
    output.mkdir(parents=True, exist_ok=False)
    code = [*sorted((ROOT / 'src/financial').glob('*.py')), Path(__file__), ROOT / 'src/services/persistent_service.py',
            ROOT / 'src/storage/registry.py', ROOT / 'scripts/run_product_development.py']
    manifest = {'label_sha256': digest(labels), 'code_sha256': {str(p.relative_to(ROOT)): digest(p) for p in code},
                'source_receipts_sha256': digest(ROOT / 'docs/fixtures/product/ingestion_receipts.v1.json'),
                'original_byte_hashes_verified': len(receipts), 'holdout': 'not_accessed',
                'api_calls': 0, 'scope': 'Live pinned Postgres domain/registry execution; not HTTP/UI or fresh generation',
                'narrative_presentation_candidate': presentation,
                'reused_narrative_results_sha256': digest(previous) if previous else None}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    old = {r['case_id']: r['result'] for r in map(json.loads, previous.read_text().splitlines())} if previous else {}
    cases = json.loads(labels.read_text())['cases']
    rows = []
    with (output / 'results.jsonl').open('x') as stream:
        for case in cases:
            started = time.monotonic()
            result = (replay_narrative(case, old[case['case_id']], registry, owner, presentation=presentation)
                      if case['lane'] == 'narrative' else execute(case, registry, owner))
            result['execution'] = {'execution_id': str(uuid4()), 'timestamp': datetime.now(timezone.utc).isoformat(),
                                   'parent_run_id': None, 'collection_id': None}
            result['run_id'] = hashlib.sha256(_canonical({k: v for k, v in result.items() if k != 'run_id'}).encode()).hexdigest()
            registry.save_research(owner, result)
            reopened = registry.research_run(owner, result['run_id'])['payload'] == result
            checks = assess(case, result)
            checks['history_reopen_equal'] = reopened
            row = {'case_id': case['case_id'], 'primary_slice': case['primary_slice'], 'tags': case['tags'],
                   'latency_seconds': time.monotonic() - started, 'history_reopen_equal': reopened,
                   'execution_kind': 'narrative_claim_replay' if case['lane'] == 'narrative' else 'fresh_deterministic',
                   'checks': checks, 'result': result}
            stream.write(json.dumps(row, ensure_ascii=False) + '\n'); stream.flush()
            rows.append(row)
    summary = {**summarize(rows), 'qualification': manifest['scope'],
               'execution_counts': {k: sum(r['execution_kind'] == k for r in rows)
                                    for k in ('fresh_deterministic', 'narrative_claim_replay')}}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, default=ROOT / 'docs/fixtures/product/development_cases.v1.json')
    parser.add_argument('--previous', type=Path, default=ROOT / 'docs/benchmarks/20261003-product-development/capture-v4/results.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--presentation-candidate', action='store_true',
                        help='Apply the proposed standalone narrative renderer; distinct from production behavior')
    args = parser.parse_args()
    frozen_cases()  # The original development freeze is validated even for extension captures.
    rows = capture(args.labels, args.output, previous=args.previous, presentation=args.presentation_candidate)
    print(json.dumps({'cases': len(rows), 'mechanical_pass': sum(all(r['checks'].values()) for r in rows), 'api_calls': 0}))
