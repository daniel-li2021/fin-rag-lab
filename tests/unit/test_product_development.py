"""Frozen development dimensions and original numeric expectations fail closed."""
import json
import pytest

from scripts.run_product_development import FIXTURE, frozen_cases, assess, summarize


def test_development_freeze_has_required_dimensions_and_original_labels():
    labels = frozen_cases()
    assert labels['numeric_cases'] == 25 and labels['narrative_cases'] == 8
    assert labels['answerable_cross_company_cases'] == 8
    for case in labels['cases']:
        if case['lane'] == 'narrative' and case['expected']['outcome'] != 'refuse':
            assert all(t['reviewed_original_candidates'] for t in case['expected']['narrative_tasks'])


def test_changed_original_manifest_is_rejected_before_capture(tmp_path):
    labels = json.loads(FIXTURE.read_text())
    labels['artifact_sha256'] = {'changed.json': 'a'*64}
    (tmp_path/'changed.json').write_text('{}')
    p = tmp_path/'labels.json';p.write_text(json.dumps(labels))
    with pytest.raises(ValueError, match='manifest has changed'):
        frozen_cases(p)


def test_numeric_checks_require_supported_card_and_dimensions_not_only_answer_text():
    case = next(c for c in frozen_cases()['cases'] if c['expected']['observations'])
    result = {'outcome': case['expected']['outcome'], 'usage': {'planner_calls': 0, 'generator_calls': 0},
              'calculations': [], 'coverage': [], 'observations': case['expected']['observations']}
    assert not assess(case,result)['numeric_original_bindings']
    result['coverage'] = [{'status': 'supported', 'observation_ids': [o['observation_id'] for o in result['observations']]}]
    assert assess(case,result)['numeric_original_bindings']
    result['observations'] = [{**o,'scope':'imaginary'} for o in result['observations']]
    assert not assess(case,result)['numeric_original_bindings']
    result['usage']['planner_calls']=1
    assert not assess(case,result)['planner_disabled']
