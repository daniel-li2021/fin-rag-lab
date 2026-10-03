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


def test_pdf_response_failures_do_not_publish_invalid_original(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus, 'fetch_snapshot', lambda url: (b'<html>Access error</html>', 'text/html', {}))
    inventory = {'reports': [{'report_id': 'report', 'split': 'development', 'url': 'https://example.com/report.pdf'}]}
    result = corpus.acquire(inventory, tmp_path)
    assert result['reports'][0]['status'] == 'unavailable'
    assert not (tmp_path / 'report.pdf').exists()


def test_review_packet_retains_original_page_text_and_rejects_hash_drift(tmp_path):
    import hashlib
    import fitz
    from scripts.prepare_financial_review import prepare
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((50, 50), 'Total revenue 12\nNet income 3\nQuarter ended March 31, 2026')
        data = document.tobytes()
    (tmp_path / 'report.pdf').write_bytes(data)
    inventory = {'reports': [{'report_id': 'report', 'report_family': 'report', 'role': 'primary', 'split': 'development'}]}
    receipts = {'inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
        'reports': [{'report_id': 'report', 'status': 'retained-unindexed', 'media_type': 'application/pdf',
                     'file_name': 'report.pdf', 'sha256': hashlib.sha256(data).hexdigest()}]}
    result = prepare(inventory, receipts, tmp_path)
    assert result['reports'][0]['pages'][0]['original_page'] == 1
    assert 'Total revenue 12' in result['reports'][0]['pages'][0]['text']
    assert result['eligible_observations'] == 0 and result['model_calls'] == 0
    (tmp_path / 'report.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='original hash'):
        prepare(inventory, receipts, tmp_path)
    with pytest.raises(ValueError, match='inventory hash'):
        prepare({'reports': []}, receipts, tmp_path)
