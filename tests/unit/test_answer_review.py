"""Portable regression: saved evidence reviews and provider receipts are replayable."""
import json
from decimal import Decimal
from pathlib import Path

from scripts.replay_answer_review import replay_review
from src.evaluators.benchmark import digest, replay


def test_phase_close_review_and_cost_replay():
    root = Path(__file__).resolve().parents[2]
    folder = root / 'docs/benchmarks/20261002-parent-bm25'
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert manifest['golden_sha256'] == digest(root / 'data/golden_set/golden.jsonl')
    assert manifest['labels_sha256'] == digest(root / 'data/golden_set/labels.v1.json')
    assert manifest['configuration']['backend'] == 'postgres'
    assert manifest['configuration']['evidence_policy'] == 'actual_quick_deep'
    assert replay(folder / 'results.jsonl') == json.loads((folder / 'summary.json').read_text())
    summary, costs = replay_review(folder)
    expected = json.loads((folder / 'reviewed_summary.json').read_text())
    assert summary == {k: v for k, v in expected.items() if k != 'review_totals'}
    measured = json.loads((folder / 'measured_cost.json').read_text())
    assert costs == [{k: row[k] for k in ('id', 'cost_usd')} for row in measured['rows']]
    assert sum(Decimal(c['cost_usd']) for c in costs) == Decimal('0.019366155')
    assert summary['all']['metrics']['numeric_accuracy'] == {'mean': .9, 'denominator': 10}
    assert summary['all']['metrics']['outcome_correctness']['mean'] == .7
    # Citation resolution must not promote the correct but incorrectly cited q08.
    review = json.loads((folder / 'review.json').read_text())['rows']
    assert review[7]['numeric_claims'] and review[7]['citation_support'] == 0
    assert not review[7]['strict_pass'] and not review[21]['strict_pass']
    docker = json.loads((root / 'docs/DOCKER_CHECK.json').read_text())
    assert docker['passed'] and docker['two_concurrent_statuses'] == [200, 200]
    assert docker['worker_check']['source_updated_without_image_rebuild']
    assert docker['worker_resource_check']['exit_code'] == 0
    assert docker['worker_resource_check']['peak_memory_bytes'] < 512 * 1024**2
