#!/usr/bin/env python3
"""Ingest only hash-verified development originals through reviewed physical windows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def verified_inputs(inventory, receipts, windows, directory):
    expected = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    if receipts['inventory_sha256'] != expected or windows['inventory_sha256'] != expected:
        raise ValueError('Development inventory hash mismatch')
    reports = {r['report_id']: r for r in inventory['reports']}
    acquired = {r['report_id']: r for r in receipts['reports']}
    if len(windows['reports']) != len(reports) or {r['report_id'] for r in windows['reports']} != set(reports):
        raise ValueError('Each development original requires exactly one reviewed window')
    verified = []
    for window in windows['reports']:
        report = reports[window['report_id']]
        receipt = acquired[window['report_id']]
        if report['split'] != 'development' or window['review_status'] != 'confirmed' or not window['reviewer']:
            raise ValueError('Only reviewed development windows can ingest')
        if receipt['status'] != 'retained-unindexed':
            raise ValueError('Original acquisition is incomplete')
        path = directory / receipt['file_name']
        if path.name != receipt['file_name'] or hashlib.sha256(path.read_bytes()).hexdigest() != window['source_sha256'] or receipt['sha256'] != window['source_sha256']:
            raise ValueError('Original/window hash mismatch')
        start, end = window['physical_pages']
        if not 1 <= start <= end <= receipt['original_pages'] or end - start + 1 > 100:
            raise ValueError('Physical window must contain 1–100 original pages')
        if window['metadata']['company_id'] != report['company_id']:
            raise ValueError('Window company differs from original inventory')
        verified.append((report, receipt, window, path))
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ingest', action='store_true', help='Explicitly perform the approved embedding calls')
    parser.add_argument('--profile', type=Path, default=ROOT / 'index/product-local/runtime.env')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/fixtures/product/ingestion_receipts.v1.json')
    args = parser.parse_args()
    directory = ROOT / 'docs/fixtures/product'
    inventory = json.loads((directory / 'development_inventory.v1.json').read_text())
    receipts = json.loads((directory / 'acquisition_receipts.v1.json').read_text())
    windows = json.loads((directory / 'indexed_windows.v1.json').read_text())
    inputs = verified_inputs(inventory, receipts, windows, ROOT / 'data/product_corpus')
    if not args.ingest:
        print(json.dumps({'reports': len(inputs), 'selected_pages': sum(w['physical_pages'][1]-w['physical_pages'][0]+1 for _,_,w,_ in inputs), 'status': 'verified-no-model-calls'}))
        return
    from dotenv import load_dotenv, dotenv_values
    load_dotenv(ROOT / '.env')
    profile = dotenv_values(args.profile)
    from src.services.persistent_service import PersistentRAGService
    from src.storage.objects import LocalObjects
    from src.observability import CostTracker
    tracker = CostTracker(pricing={'text-embedding-3-small': {'input': .00002, 'output': 0}})
    owner = profile['FINRAG_OWNER']
    svc = PersistentRAGService(profile['DATABASE_URL'], owner=owner,
        objects=LocalObjects(profile['FINRAG_OBJECT_DIR']), cost_tracker=tracker,
        cache_root=ROOT / 'cache', index_dir=ROOT / 'index/product-local')
    previous = json.loads(args.output.read_text()) if args.output.exists() else {'reports': []}
    old = {r['report_id']: r for r in previous['reports']}
    result = {'schema_version': 1, 'owner': owner, 'backend': 'local-postgres', 'release_decision': 'held',
              'captured_at': datetime.now(timezone.utc).isoformat(), 'windows_sha256': hashlib.sha256((directory / 'indexed_windows.v1.json').read_bytes()).hexdigest(),
              'captioner': 'NoOpCaptioner', 'reports': []}
    for report, receipt, window, path in inputs:
        started = time.monotonic()
        source = svc.register(kind='pdf', title=f"{window['metadata']['company_name']} {report['period_label']} {report['document_type']}",
                              locator=path.name, metadata=window['metadata'], request_key='development:'+report['report_id'])
        queued = svc.submit(source['source_id'], path.read_bytes(), media_type='application/pdf',
                            provenance={**receipt['provenance'], 'report_id': report['report_id'],
                                        'report_family': report['report_family'], 'role': report['role'],
                                        'window_review_revision': window['review_revision']},
                            max_pages=100, page_range=tuple(window['physical_pages']))
        row = {'report_id': report['report_id'], 'source_id': str(source['source_id']),
               'version_id': str(queued['version']['version_id']), 'build_id': str(queued['build']['build_id']),
               'job_id': str(queued['job']['job_id']), 'source_sha256': receipt['sha256'],
               'physical_pages': window['physical_pages'], 'original_pages': receipt['original_pages']}
        try:
            outcome = svc.process_job(queued['job']['job_id'])
            if outcome['status'] != 'ready':
                raise RuntimeError('The source job is still owned by another worker')
            row.update(outcome)
            if outcome['reused']:
                with svc.registry.connect() as db:
                    stored = db.execute('SELECT usage FROM ingestion_jobs WHERE job_id=%s', (queued['job']['job_id'],)).fetchone()
                row['usage'] = stored['usage']
                row['ingestion_latency_seconds'] = old.get(report['report_id'], {}).get('ingestion_latency_seconds')
                with svc.registry.connect() as db:
                    row['n_children'] = db.execute('SELECT count(*) FROM chunks WHERE build_id=%s AND parent_id IS NOT NULL', (queued['build']['build_id'],)).fetchone()['count']
            else:
                row['ingestion_latency_seconds'] = round(time.monotonic()-started, 3)
        except Exception as exc:
            row.update(status='failed', error=type(exc).__name__, ingestion_latency_seconds=round(time.monotonic()-started, 3))
            result['reports'].append(row)
            args.output.write_text(json.dumps(result, indent=2)+'\n')
            raise
        result['reports'].append(row)
        result['this_invocation_usage'] = tracker.report()
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k: row.get(k) for k in ('report_id','status','reused','n_children','ingestion_latency_seconds')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
