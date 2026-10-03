#!/usr/bin/env python3
"""Replay source-reviewed answers and measured token costs without model calls."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.evaluators.benchmark import score, summarize


def replay_review(folder):
    folder = Path(folder)
    raw = (folder / 'results.jsonl').read_bytes()
    review = json.loads((folder / 'review.json').read_text())
    prices = json.loads((folder / 'measured_cost.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == review['results_sha256'] == prices['results_sha256']
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert [r['id'] for r in rows] == [r['id'] for r in review['rows']]
    costs = []
    for row, audit in zip(rows, review['rows']):
        result = row['result']
        assert hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest() == audit['result_sha256']
        claims = audit['claim_reviews']
        unsupported = sum(not c['context_supported'] for c in claims)
        assert unsupported == audit['unsupported_assertions']
        result.update(numeric_claims=audit['numeric_claims'], citation_support=audit['citation_support'],
                      wrong_period_scope_assertions=audit['wrong_period_scope_assertions'],
                      hallucination={'n_refuted': unsupported, 'n_unsupported': 0},
                      metrics={'rubric_accuracy': float(audit['rubric_pass']),
                               'strict_answer_accuracy': float(audit['strict_pass']),
                               'faithfulness': sum(c['context_supported'] for c in claims) / len(claims) if claims else None})
        row['metrics'] = score(row['label'], result)
        total = Decimal(0)
        for event in result['usage']['events']:
            usage = (event.get('raw_usage') or {}).get('usage') or {}
            details = usage.get('prompt_tokens_details') or usage.get('input_token_details') or {}
            cached = details.get('cached_tokens', details.get('cache_read', 0))
            writes = details.get('cache_write_tokens', 0)
            uncached = event['input_tokens'] - cached - writes
            assert min(cached, writes, uncached) >= 0
            tariff = prices['tariff_usd_per_million'][event['model']]
            total += (Decimal(uncached) * Decimal(tariff['input'])
                      + Decimal(cached) * Decimal(tariff.get('cached_input', '0'))
                      + Decimal(writes) * Decimal(tariff.get('cache_write', '0'))
                      + Decimal(event['output_tokens']) * Decimal(tariff.get('output', '0'))) / 1_000_000
        costs.append({'id': row['id'], 'cost_usd': str(total)})
    return summarize(rows), costs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    summary, costs = replay_review(parser.parse_args().run_dir)
    print(json.dumps({'metrics': summary['all']['metrics'],
                      'measured_cost_usd': str(sum(Decimal(c['cost_usd']) for c in costs))}, indent=2))
