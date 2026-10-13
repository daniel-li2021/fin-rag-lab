"""Execute the five existing development demos without provider calls.

New directories only. Narrative text and semantic review are reused after exact
parity; these executions do not add cases to any accuracy denominator.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rerun_product_offline import capture
from scripts.replay_product_review import digest, replay as review_replay
from scripts.run_product_development import frozen_cases
from scripts.check_authentic_source_change import capture as source_capture, replay as source_replay

BASE = ROOT / 'docs/benchmarks/20261004-authentic-gaps'
FIXTURES = ROOT / 'docs/fixtures/product'
GROUPS = [
    ('common-equity', 'extension', 'development_extension.v1.json', ['ext-03']),
    ('recast-quarters', 'extension', 'development_extension.v1.json', ['ext-06', 'ext-07']),
    ('partial-coverage', 'gaps-corrected', 'development_gaps.v2.json', ['gap-04', 'gap-05', 'gap-06']),
    ('period-narrative', 'core', 'development_cases.v1.json', ['dev-15']),
]


def write(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def run(output):
    frozen_cases()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'scope': 'Five existing development demonstrations; no new accuracy denominator',
                'captured_at': datetime.now(timezone.utc).isoformat(),
                'holdout': 'not_accessed', 'provider_calls': 0, 'artifacts': {},
                'code_sha256': {str(Path(__file__).relative_to(ROOT)): digest(Path(__file__))}}
    write(output / 'manifest.json', manifest)
    scenarios = []
    for name, folder, filename, ids in GROUPS:
        labels = FIXTURES / filename
        reviewed = BASE / folder
        # Validate complete existing review custody before selecting demo steps.
        review_replay(reviewed, labels)
        cases = json.loads(labels.read_text())['cases']
        selected = [next(c for c in cases if c['case_id'] == case_id) for case_id in ids]
        subset = output / f'{name}-steps.json'
        write(subset, {'qualification': 'Subset of existing development labels; not a new split',
                       'original_labels_path': str(labels.relative_to(ROOT)),
                       'original_labels_sha256': digest(labels), 'cases': selected})
        rows = capture(subset, output / name, previous=reviewed / 'results.jsonl')
        previous = {r['case_id']: r for r in map(json.loads, (reviewed / 'results.jsonl').read_text().splitlines())}
        checks = {}
        for row in rows:
            old, new = previous[row['case_id']]['result'], row['result']
            checks[row['case_id']] = {
                'mechanical_checks': all(row['checks'].values()),
                'exact_reviewed_answer': new['answer'] == old['answer'],
                'exact_claims': new.get('claims', []) == old.get('claims', []),
                'exact_calculations': new['calculations'] == old['calculations'],
                'exact_citations': new['citations'] == old['citations'],
                'new_history_run': new['run_id'] != old['run_id'],
                'history_reopen_equal': row['history_reopen_equal'],
            }
        scenarios.append({'scenario': name, 'step_ids': ids, 'checks': checks,
                          'passed': all(all(c.values()) for c in checks.values()),
                          'review_provenance': 'Existing named development review reused after exact parity',
                          'original_review_sha256': digest(reviewed / 'review.json'),
                          'original_results_sha256': digest(reviewed / 'results.jsonl')})
    source_capture(output / 'source-change')
    transition = source_replay(output / 'source-change')
    scenarios.append({'scenario': 'source-change', 'passed': transition['passed'] == transition['checks'],
                      'lifecycle_checks': transition['checks'],
                      'qualification': 'Fresh controlled original-byte import; cached vectors; separate owner; not live URL refresh'})
    summary = {'demonstrations_passed': sum(s['passed'] for s in scenarios), 'demonstration_count': 5,
               'existing_case_steps': 7, 'scenarios': scenarios, 'provider_calls': 0,
               'fresh_narrative_generations': 0, 'holdout_executed': 0,
               'qualification': 'Domain/registry executions and exact history reopens; no HTTP/UI benchmark; no extra semantic successes'}
    write(output / 'summary.json', summary)
    # Final hash envelope also covers labels, failures and all execution manifests.
    write(output / 'integrity.json', {str(p.relative_to(output)): digest(p)
                                     for p in sorted(output.rglob('*')) if p.is_file()})
    return replay(output)


def replay(output):
    for filename, expected in json.loads((output / 'integrity.json').read_text()).items():
        target = (output / filename).resolve()
        if not target.is_relative_to(output.resolve()) or digest(target) != expected:
            raise ValueError('Demonstration artifact hash mismatch')
    summary = json.loads((output / 'summary.json').read_text())
    if summary['demonstration_count'] != 5 or summary['demonstrations_passed'] != 5:
        raise ValueError('Demonstration failures retained; cannot report five passes')
    for name, folder, filename, ids in GROUPS:
        subset = json.loads((output / f'{name}-steps.json').read_text())
        labels = FIXTURES / filename
        if subset['original_labels_sha256'] != digest(labels):
            raise ValueError('Original development labels changed')
        original = {c['case_id']: c for c in json.loads(labels.read_text())['cases']}
        if subset['cases'] != [original[case_id] for case_id in ids]:
            raise ValueError('Demo steps differ from original frozen cases')
        review_replay(BASE / folder, labels)
    source_replay(output / 'source-change')
    return {'demonstrations_passed': 5, 'demonstration_count': 5,
            'existing_case_steps': 7, 'provider_calls': 0, 'holdout_executed': 0,
            'qualification': 'Hash-bound saved demo verification; no fresh execution on replay'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--output', type=Path)
    modes.add_argument('--replay', type=Path)
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(args.replay)))
    else:
        try:
            print(json.dumps(run(args.output)))
        except Exception as exc:
            if args.output.is_dir():
                write(args.output / 'failure.json', {'exception': type(exc).__name__, 'message': str(exc),
                                                     'qualification': 'All partial outputs retained'})
            raise
