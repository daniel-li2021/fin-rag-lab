"""Acquisition never authorizes facts or silently consumes a holdout."""
import json
from pathlib import Path

import pytest

from scripts import prepare_product_corpus as corpus


def test_frozen_inventory_has_exact_development_budget_and_families():
    inventory = json.loads(corpus.INVENTORY.read_text())
    reports = inventory['reports']
    assert len(reports) == 22 and len({r['report_id'] for r in reports}) == 22
    assert sum(r['role'] == 'primary' for r in reports) == 18
    assert len({r['report_family'] for r in reports}) == 18
    assert all(r['split'] == 'development' and not r['indexed_pages'] and r['review_status'] == 'unreviewed' for r in reports)
    assert inventory['holdout']['status'] == 'reserve-not-acquired-not-sealed'


def test_acquisition_reuses_verified_bytes_and_records_failures(tmp_path, monkeypatch):
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith('blocked'):
            raise ValueError('Snapshot HTTP status 403')
        return b'<html><body>Original report</body></html>', 'text/html', {'original_url': url}
    monkeypatch.setattr(corpus, 'fetch_snapshot', fetch)
    inventory = {'reports': [{'report_id': name, 'split': 'development', 'url': url} for name, url in
        [('good', 'https://example.com/good'), ('blocked', 'https://example.com/blocked'), ('unresolved', None)]]}
    first = corpus.acquire(inventory, tmp_path)
    assert first['reports'][0]['status'] == 'retained-unindexed'
    assert all(r['eligible_observations'] == 0 and not r['indexed_pages'] for r in first['reports'])
    assert all(r['status'] == 'unavailable' for r in first['reports'][1:])
    second = corpus.acquire(inventory, tmp_path, first)
    assert calls.count('https://example.com/good') == 1
    assert second['reports'][0]['reused'] and second['release_decision'] == 'held'
    assert second['model_calls'] == 0
    with pytest.raises(ValueError, match='holdout'):
        corpus.acquire({'reports': [{'report_id': 'sealed', 'split': 'holdout'}]}, tmp_path)
