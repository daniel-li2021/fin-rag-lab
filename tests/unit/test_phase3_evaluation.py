"""Frozen evaluation cannot confuse integrity, synthetic volume and release quality."""
import copy
import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_phase3_evaluation import DEFAULT_MANIFEST, ROOT, check_cases, validate_manifest


def test_frozen_inputs_splits_and_authentic_release_denominators():
    manifest = json.loads(DEFAULT_MANIFEST.read_text())
    report = validate_manifest(manifest)
    assert report['integrity'] == 'passed', report['errors']
    assert report['release_decision'] == 'held'
    assert report['corpus_gate']['status'] == 'not_assessable'
    assert report['corpus_gate']['authentic_holdout'] == 0
    assert report['eligible_authentic_observations'] == 0
    assert report['answer_accuracy'] == report['cost_latency'] == 'not_assessable'

    changed = copy.deepcopy(manifest)
    changed['immutable_files'][manifest['cases_path']] = '0' * 64
    assert validate_manifest(changed)['integrity'] == 'failed'
    changed = copy.deepcopy(manifest)
    changed['design']['minimum_authentic_numeric_holdout'] = 1
    assert validate_manifest(changed)['integrity'] == 'failed'
    changed = copy.deepcopy(manifest)
    changed['immutable_files']['../outside-repository'] = '0' * 64
    assert any('escapes repository' in e for e in validate_manifest(changed)['errors'])

    cases = json.loads((ROOT / manifest['cases_path']).read_text())['cases']
    holdout = dict(cases[0], id='leaked-holdout', split='holdout')
    errors, _ = check_cases(cases + [holdout])
    assert any('report_families overlaps' in e for e in errors)
    assert any('company_period_keys overlaps' in e for e in errors)
    assert any('revision_lineages overlaps' in e for e in errors)
    assert any('incomplete frozen holdout label' in e for e in errors)

    synthetic = [dict(holdout, id=f'synthetic-{i}', authentic=False,
                      report_families=[f'report-{i}'], company_period_keys=[f'period-{i}'],
                      revision_lineages=[f'lineage-{i}']) for i in range(20)]
    _, readiness = check_cases(cases + synthetic)
    assert readiness['authentic_numeric_holdout'] == 0
    assert readiness['status'] == 'not_assessable'


    # A hash-correct sidecar can still be malformed: fail closed on its content.
    sidecar = json.loads((ROOT / manifest['observations_path']).read_text())
    with TemporaryDirectory(dir=ROOT / 'docs/fixtures/phase3') as folder:
        path = Path(folder) / 'malformed.json'
        relative = str(path.relative_to(ROOT))
        for field, value in [('value', 'not-a-decimal'),
                             ('verification_status', 'approved'),
                             ('verification_status', 'reviewed')]:
            changed_sidecar = copy.deepcopy(sidecar)
            changed_sidecar['observations'][0][field] = value
            path.write_text(json.dumps(changed_sidecar))
            changed = copy.deepcopy(manifest)
            changed['observations_path'] = relative
            changed['immutable_files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            report = validate_manifest(changed)
            assert report['integrity'] == 'failed'
            assert report['eligible_authentic_observations'] == 0
