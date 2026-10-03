#!/usr/bin/env python3
"""Acquire the frozen development inventory; no parsing, embeddings, fact promotion or holdout access."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.storage.fetch import fetch_snapshot

INVENTORY = ROOT / 'docs/fixtures/product/development_inventory.v1.json'


def acquire(inventory, destination, previous=None):
    previous = {r['report_id']: r for r in (previous or {}).get('reports', [])}
    destination.mkdir(parents=True, exist_ok=True)
    receipts = []
    for report in inventory['reports']:
        if report['split'] != 'development':
            raise ValueError('This command cannot acquire holdout sources')
        old = previous.get(report['report_id'], {})
        path = destination / (report['report_id'] + ('.pdf' if (report['url'] or '').endswith('.pdf') else '.html'))
        receipt = {'report_id': report['report_id'], 'url': report['url'], 'status': 'unavailable',
                   'indexed_pages': [], 'eligible_observations': 0}
        if not report['url']:
            receipt['error'] = 'Official download URL requires resolution from entry page'
        elif path.exists() and old.get('url') == report['url'] and hashlib.sha256(path.read_bytes()).hexdigest() == old.get('sha256'):
            receipt = {**old, 'reused': True}
        else:
            try:
                data, media, provenance = fetch_snapshot(report['url'])
                if report['url'].endswith('.pdf') and media != 'application/pdf':
                    raise ValueError('Expected a PDF original, received another media type')
                if media == 'application/pdf' and not data.startswith(b'%PDF-'):
                    raise ValueError('Response is not a PDF original')
                if media == 'text/html' and b'<html' not in data.lower()[:10000]:
                    raise ValueError('Response is not an HTML original')
                receipt.update(status='retained-unindexed', sha256=hashlib.sha256(data).hexdigest(),
                    size_bytes=len(data), media_type=media, provenance=provenance, file_name=path.name, reused=False)
                if media == 'application/pdf':
                    import fitz
                    with fitz.open(stream=data, filetype='pdf') as document:
                        receipt['original_pages'] = len(document)
                        receipt['requires_page_selection'] = len(document) > 100
                path.write_bytes(data)
            except (ValueError, OSError, TimeoutError, RuntimeError) as exc:
                receipt = {'report_id': report['report_id'], 'url': report['url'], 'status': 'unavailable',
                           'indexed_pages': [], 'eligible_observations': 0, 'error': str(exc)}
        receipts.append(receipt)
    return {'schema_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
            'reports': receipts, 'release_decision': 'held', 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquire', action='store_true', help='Explicitly fetch originals; repeated valid receipts reuse bytes')
    parser.add_argument('--destination', type=Path, default=ROOT / 'data/product_corpus')
    parser.add_argument('--receipts', type=Path, default=ROOT / 'docs/fixtures/product/acquisition_receipts.v1.json')
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    if not args.acquire:
        print(json.dumps({'development_reports': len(inventory['reports']), 'status': 'preview-no-fetch'}, indent=2))
        return
    previous = json.loads(args.receipts.read_text()) if args.receipts.exists() else None
    result = acquire(inventory, args.destination, previous)
    args.receipts.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'retained': sum(r['status'] == 'retained-unindexed' for r in result['reports']),
                      'unavailable': sum(r['status'] == 'unavailable' for r in result['reports']), 'model_calls': 0}))


if __name__ == '__main__':
    main()
