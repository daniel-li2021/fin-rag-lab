#!/usr/bin/env python3
"""Prepare original-page candidates for human review; never create eligible observation cards."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ANCHORS = ('net revenue', 'total revenue', 'net income', 'gross profit', 'gross margin',
           'operating income', 'net interest income', 'provision for credit losses', 'data center', 'client and gaming')


def page_candidates(data, limit=6):
    """Keep whole pages and table geometry: reading order alone cannot bind a table cell."""
    candidates = []
    with fitz.open(stream=data, filetype='pdf') as document:
        for number, page in enumerate(document, 1):
            text = page.get_text('text', sort=True)
            anchors = [anchor for anchor in ANCHORS if anchor in text.lower()]
            if anchors:
                candidates.append({'original_page': number, 'text': text, 'anchor_matches': anchors})
        candidates.sort(key=lambda page: (-len(page['anchor_matches']), page['original_page']))
        candidates = sorted(candidates[:limit], key=lambda page: page['original_page'])
        for candidate in candidates:
            page = document[candidate['original_page'] - 1]
            try:
                candidate['tables'] = [{'bbox': list(table.bbox), 'cells': table.extract()}
                                       for table in page.find_tables().tables]
            except Exception as exc:
                candidate['tables'] = []
                candidate['table_extraction_error'] = str(exc)
    return candidates


def prepare(inventory, receipts, directory):
    if receipts['inventory_sha256'] != hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest():
        raise ValueError('Acquisition inventory hash mismatch')
    by_id = {report['report_id']: report for report in inventory['reports']}
    prepared = []
    for receipt in receipts['reports']:
        report = by_id[receipt['report_id']]
        if report['split'] != 'development':
            raise ValueError('Development review cannot read holdout sources')
        entry = {'report_id': report['report_id'], 'report_family': report['report_family'],
                 'status': 'unavailable', 'eligible_observations': 0, 'pages': []}
        if receipt['status'] == 'retained-unindexed' and receipt['media_type'] == 'application/pdf':
            data = (directory / receipt['file_name']).read_bytes()
            if hashlib.sha256(data).hexdigest() != receipt['sha256']:
                raise ValueError('Retained original hash mismatch')
            entry.update(status='unreviewed-candidates', source_sha256=receipt['sha256'],
                         original_file=receipt['file_name'], pages=page_candidates(data, 8 if report['role'] == 'companion' else 6))
        else:
            entry['reason'] = receipt.get('error', 'No supported retained PDF original')
        prepared.append(entry)
    return {'schema_version': 1, 'policy': 'original-page-candidates-v1', 'extractor': 'PyMuPDF ' + fitz.VersionBind,
            'qualification': 'Candidates require visual row/column, dates, scope, basis, definition and independent review. '
                             'These page candidates are not build blocks or eligible FinancialObservation cards.',
            'reports': prepared, 'model_calls': 0, 'eligible_observations': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'data/product_corpus')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/product_corpus/review_packet.v1.json')
    args = parser.parse_args()
    inventory = json.loads((ROOT / 'docs/fixtures/product/development_inventory.v1.json').read_text())
    receipts = json.loads((ROOT / 'docs/fixtures/product/acquisition_receipts.v1.json').read_text())
    result = prepare(inventory, receipts, args.directory)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    summary = {'packet_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
               'retained_reports': sum(r['status'] == 'unreviewed-candidates' for r in result['reports']),
               'candidate_pages': sum(len(r['pages']) for r in result['reports']),
               'candidate_tables': sum(len(p['tables']) for r in result['reports'] for p in r['pages']),
               'eligible_observations': 0, 'model_calls': 0,
               'report_pages': {r['report_id']: [p['original_page'] for p in r['pages']] for r in result['reports']}}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
