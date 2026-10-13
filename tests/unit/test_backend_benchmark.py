import pytest
from scripts.benchmark_backend_offline import distribution, verified_content


def test_timing_quantiles_use_median_and_nearest_rank():
    result = distribution([i / 1000 for i in range(1, 101)])
    assert result['n'] == 100
    assert result['p50_ms'] == pytest.approx(50.5)
    assert result['p95_ms'] == pytest.approx(95)
    assert distribution([.01, .02])['p95_ms'] is None


def test_review_reuse_rejects_changed_financial_content(monkeypatch):
    monkeypatch.setattr('scripts.benchmark_backend_offline.assess', lambda *_: {'mechanical': True})
    case = {'case_id': 'parity-boundary'}
    expected = {'answer': '$42m', 'citations': {'fact': {'version_id': 'original'}}}
    assert len(verified_content(case, dict(expected), expected)) == 64
    with pytest.raises(ValueError, match='citations'):
        verified_content(case, {**expected, 'citations': {'fact': {'version_id': 'changed'}}}, expected)
    with pytest.raises(ValueError, match='answer'):
        verified_content(case, {**expected, 'answer': '$43m'}, expected)
