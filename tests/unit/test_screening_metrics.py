"""Replay the published screening metrics without ignored caches, SQL or model calls."""
import hashlib
import json
from pathlib import Path

import pytest

from src.evaluators.benchmark import load_benchmark, score, summarize, latency_summary

ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return json.loads((ROOT / relative).read_text())


@pytest.mark.parametrize('arm', 'ABCD')
def test_published_contextual_metrics_replay_from_original_evidence(arm):
    examples, _ = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    fixture = read('data/golden_set/retrieval_screen.v1.json')
    report = read('docs/CONTEXTUAL_CHECK.json')
    assert fixture['labels_sha256'] == hashlib.sha256((ROOT / 'data/golden_set/labels.v1.json').read_bytes()).hexdigest()
    assert report['run_manifest']['labels_sha256'] == fixture['labels_sha256']
    assert [r['id'] for r in fixture['arms'][arm]] == [e['id'] for e in examples]
    rows = [{**r, 'category': e['category'], 'metrics': score(e, r['result'])}
            for e, r in zip(examples, fixture['arms'][arm])]
    assert summarize(rows)['all'] == report['arms'][arm]['summary']
    if arm != 'A':
        pairs = [{'id': e['id'], 'recall_delta': score(e, r['result'])['evidence_recall_final']
                  - score(e, a['result'])['evidence_recall_final'] if e['evidence'] else None}
                 for e, r, a in zip(examples, fixture['arms'][arm], fixture['arms']['A'])]
        assert pairs == report['paired_deltas'][arm]
        assert report['macro_recall_deltas'][arm] == pytest.approx(
            sum(p['recall_delta'] for p in pairs if p['recall_delta'] is not None) / 26)
        assert report['macro_recall_deltas'][arm] < .10
    assert report['decision'] == 'retain_parent_child'
    assert report['promotion_status'] == 'recall_gate_failed'


def test_cached_context_usage_counts_completion_once_and_preserves_unknown_cost():
    fixture = read('data/golden_set/retrieval_screen.v1.json')
    report = read('docs/CONTEXTUAL_CHECK.json')
    events = fixture['context_usage_events']
    assert report['all_cached_context_usage'] == {
        'calls': len(events), 'input_tokens': sum(e['input_tokens'] for e in events),
        'output_tokens': sum(e['output_tokens'] for e in events),
        'unknown_cost_calls': sum(e['cost_usd'] is None for e in events),
        'cost_usd': sum(e['cost_usd'] for e in events) if all(e['cost_usd'] is not None for e in events) else None}
    assert report['all_cached_context_usage']['cost_usd'] is None


def test_lexical_summary_parity_and_paired_deltas():
    report = read('docs/LEXICAL_CHECK.json')
    examples, _ = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    reference = read('data/golden_set/retrieval_screen.v1.json')['arms']['A']
    rows = report['questions']
    assert [r['id'] for r in rows] == [e['id'] for e in examples]
    for branch in ('bm25', 'postgres'):
        values = [r['branches'][branch]['final_recall'] for r in rows if r['branches'][branch]['final_recall'] is not None]
        assert report['summary'][branch] == {
            'macro_recall': sum(values) / len(values), 'denominator': len(values),
            'latency_ms': latency_summary([r['branches'][branch]['latency_ms'] for r in rows])}
    for e, row, a, pair in zip(examples, rows, reference, report['paired_deltas']):
        bm25, pg = row['branches']['bm25'], row['branches']['postgres']
        assert bm25['final_recall'] == score(e, a['result'])['evidence_recall_final']
        assert bm25['candidate_ids'] == [c['chunk_id'] for c in a['result']['candidates']]
        assert pair == {'id': e['id'], 'recall_delta': pg['final_recall'] - bm25['final_recall'] if e['evidence'] else None,
                        'ranking_changed': pg['candidate_ids'] != bm25['candidate_ids']}
    assert report['vector_reference_parity']['identical_rankings'] == len(rows) == 30
    assert report['decision'] == 'retain_bm25'


def test_metadata_totals_are_exact_field_matches_and_abstentions():
    report = read('docs/METADATA_CHECK.json')
    for row in report['cases']:
        assert row['correct_fields'] == sum(row['actual'][k] == v for k, v in row['expected'].items())
        assert row['abstentions'] == sum(v is None for v in row['actual'].values())
    assert report['correct_fields'] == sum(r['correct_fields'] for r in report['cases']) == 23
    assert report['field_denominator'] == sum(len(r['expected']) for r in report['cases']) == 24
    assert report['abstentions'] == sum(r['abstentions'] for r in report['cases']) == 8
    assert report['synthetic_only']
