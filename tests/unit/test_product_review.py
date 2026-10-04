"""Saved authentic review replay must reject missing or mismatched attestations."""
import json
from pathlib import Path

import pytest

from scripts.replay_product_review import digest, replay

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / 'docs/benchmarks/20261003-authentic-development'
LABELS = ROOT / 'docs/fixtures/product/development_cases.v1.json'


def test_paired_development_review_preserves_losses_and_all_denominators():
    before = replay(BENCHMARK / 'baseline', LABELS)
    after = replay(BENCHMARK / 'regression', LABELS)
    assert before['strict_authentic_development']['passed'] == 37
    assert after['strict_authentic_development'] == {'passed': 45, 'denominator': 48, 'value': .9375}
    candidate = replay(BENCHMARK / 'presentation-candidate', LABELS)
    assert candidate['strict_authentic_development'] == {'passed': 48, 'denominator': 48, 'value': 1.0}
    assert before['failure_classes'] == {'answer_period_distinction_missing': 3,
        'answer_duration_qualification_missing': 2, 'clarification_gap_not_precise': 6}
    assert after['numeric_accuracy']['denominator'] == 25
    assert after['narrative_claim_support']['denominator'] == 12
    assert after['issued_operand_coverage']['denominator'] == 22
    assert after['distinct_required_multi_document']['denominator'] == 13
    assert after['independent_release_reviews'] == 0 and after['release_decision'] == 'held'
    assert after['coverage_limits']['authentic_source_change_staleness_cases'] == 0
    extended = replay(BENCHMARK / 'extension', ROOT / 'docs/fixtures/product/development_extension.v1.json')
    assert extended['strict_authentic_development']['passed'] == 16
    assert extended['distinct_required_multi_document']['denominator'] == 12


def review_copy(tmp_path):
    original = BENCHMARK / 'regression'
    (tmp_path / 'results.jsonl').write_bytes((original / 'results.jsonl').read_bytes())
    review = json.loads((original / 'review.json').read_text())
    review['results_file'] = 'results.jsonl'
    return review


def test_semantic_unknown_cannot_be_counted_as_a_pass(tmp_path):
    review = review_copy(tmp_path)
    review['cases'][0]['original_binding_support'] = None
    (tmp_path / 'review.json').write_text(json.dumps(review))
    with pytest.raises(ValueError, match='unassessable'):
        replay(tmp_path, LABELS)


def test_changed_result_or_unreviewed_claim_is_rejected(tmp_path):
    review = review_copy(tmp_path)
    review['cases'][4]['claim_support'] = []
    (tmp_path / 'review.json').write_text(json.dumps(review))
    with pytest.raises(ValueError, match='Every issued narrative claim'):
        replay(tmp_path, LABELS)
    review = review_copy(tmp_path)
    with (tmp_path / 'results.jsonl').open('a') as stream:
        stream.write('\n')
    (tmp_path / 'review.json').write_text(json.dumps(review))
    with pytest.raises(ValueError, match='not bound'):
        replay(tmp_path, LABELS)
