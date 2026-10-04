"""Bad development receipts/windows fail before any ingestion or paid work."""
import hashlib
import json

import pytest

from scripts.ingest_product_corpus import verified_inputs


def test_windows_require_original_hash_review_and_development_split(tmp_path):
    data = b'%PDF-original'
    (tmp_path / 'one.pdf').write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    inventory = {'reports': [{'report_id': 'one', 'company_id': 'AMD', 'split': 'development'}]}
    ih = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    receipts = {'inventory_sha256': ih, 'reports': [{'report_id': 'one', 'status': 'retained-unindexed',
                'file_name': 'one.pdf', 'sha256': digest, 'original_pages': 138}]}
    window = {'report_id': 'one', 'source_sha256': digest, 'physical_pages': [37, 89],
              'review_status': 'confirmed', 'reviewer': 'Codex', 'metadata': {'company_id': 'AMD'}}
    windows = {'inventory_sha256': ih, 'reports': [window]}
    assert len(verified_inputs(inventory, receipts, windows, tmp_path)) == 1
    window['physical_pages'] = [1, 138]
    with pytest.raises(ValueError, match='1–100'):
        verified_inputs(inventory, receipts, windows, tmp_path)
    window['physical_pages'] = [37, 89]
    window['review_status'] = 'unreviewed'
    with pytest.raises(ValueError, match='reviewed development'):
        verified_inputs(inventory, receipts, windows, tmp_path)
    window['review_status'] = 'confirmed'
    (tmp_path / 'one.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        verified_inputs(inventory, receipts, windows, tmp_path)
