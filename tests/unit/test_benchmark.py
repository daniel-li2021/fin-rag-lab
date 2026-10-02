import json
from pathlib import Path

import pytest
from src.evaluators.benchmark import latency_summary, load_benchmark, manifest, replay, run_benchmark, score, summarize

ROOT = Path(__file__).resolve().parents[2]


def test_labels_and_manifest_are_bound_to_original_corpus():
    examples, overlay = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    assert len(examples) == 30
    assert len({e['id'] for e in examples}) == 30
    assert all(e['required_sources'] and 'any' not in e['required_sources'] for e in examples if e['category'] == 'cross_doc')
    assert all(e['numeric'] for e in examples[:10])
    config = {'arm': 'test'}
    a = manifest(ROOT, ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json', config, overlay['corpus'])
    b = manifest(ROOT, ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json', {'arm': 'changed'}, overlay['corpus'])
    assert a['code_sha256'] == b['code_sha256']
    assert a['configuration_sha256'] != b['configuration_sha256']
    # Every quote is an exact source span in the pinned original PDF.
    import fitz
    for e in examples:
        for span in e['evidence']:
            with fitz.open(ROOT / overlay['corpus'][span['source']]['path']) as doc:
                text = doc[span['page_number'] - 1].get_text()
                assert text[span['char_start']:span['char_end']] == span['quote']


def test_capture_replay_denominators_and_no_overwrite(tmp_path):
    examples, _ = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    calls = []
    def query(q):
        calls.append(q)
        return {'answer': 'unsupported', 'outcome': 'refuse', 'chunks': [], 'candidates': [], 'usage': [], 'metrics': {'context_recall': 1}}
    summary = run_benchmark([examples[0], examples[-1]], query, tmp_path, {'schema_version': 1})
    assert len(calls) == 2
    assert replay(tmp_path / 'results.jsonl') == summary
    assert summary['all']['metrics']['context_recall']['denominator'] == 1
    assert summary['all']['metrics']['numeric_accuracy'] == {'mean': None, 'denominator': 0}
    with pytest.raises(FileExistsError):
        run_benchmark(examples, query, tmp_path, {})


def test_evidence_and_numeric_scoring_reject_wrong_version_period_and_scope():
    examples, _ = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    e = examples[0]
    chunk = {'evidence_spans': [dict(e['evidence'][0], text=e['evidence'][0]['quote'])]}
    claim = {k:v for k,v in e['numeric'][0].items() if k != 'tolerance'}
    result = {'chunks': [chunk, chunk], 'candidates': [chunk], 'outcome': 'answer', 'numeric_claims': [claim]}
    assert score(e, result)['evidence_recall_final'] == 1
    assert score(e, result)['numeric_accuracy'] == 1
    claim['period'] = 'Q4 2024'
    chunk['evidence_spans'][0]['source_version'] = 'wrong'
    assert score(e, result)['numeric_accuracy'] == 0
    assert score(e, result)['evidence_recall_final'] == 0


def test_reporting_keeps_unknown_cost_and_unsupported_refusal_distinct(tmp_path):
    from src.evaluators.benchmark import serializable
    examples, _ = load_benchmark(ROOT / 'data/golden_set/golden.jsonl', ROOT / 'data/golden_set/labels.v1.json')
    from src.observability import CostTracker
    ct = CostTracker()
    ct.record_llm('query', 'unknown', 100, 50, 20)
    result = {'answer': 'refusal with an unsupported claim', 'outcome': 'refuse',
              'chunks': [], 'cost_usd': None, 'usage': ct.report(),
              'hallucination': {'n_unsupported': 1, 'n_refuted': 0},
              'latency_ms': 100, 'retrieval_latency_ms': 20,
              'metrics': {'faithfulness': float('nan')}}
    summary = run_benchmark(examples[-1:], lambda _: result, tmp_path, {})
    assert summary == replay(tmp_path / 'results.jsonl')
    group = summary['all']
    assert group['cost']['mean_query_cost_usd'] is None
    assert group['usage']['output_tokens'] == 50
    assert group['usage']['reasoning_tokens'] == 20  # subset, never added to output
    assert group['metrics']['outcome_accuracy']['mean'] == 1
    assert group['metrics']['outcome_correctness']['mean'] == 0
    assert group['metrics']['unsupported_assertions']['mean'] == 1
    assert group['latency_ms']['end_to_end']['p95'] == 100
    assert group['metrics']['faithfulness']['denominator'] == 0
    assert serializable(float('nan')) is None


def test_recall_mrr_and_complete_evidence_require_every_original_span():
    label = {'evidence': [
        {'source_version': 'A', 'page_number': 1, 'quote': 'Revenue 42'},
        {'source_version': 'B', 'page_number': 2, 'quote': 'Cash 8'}],
        'numeric': [], 'expected_outcome': 'answer'}
    a, b = [{'evidence_spans': [{**e, 'text': e['quote']}]} for e in label['evidence']]
    metrics = score(label, {'candidates': [{}, a, a], 'chunks': [a, a]})
    assert metrics['evidence_recall_at20'] == .5
    assert metrics['evidence_recall_final'] == .5
    assert metrics['mrr'] == .5
    assert metrics['complete_evidence'] == 0
    assert score(label, {'chunks': [a, b]})['complete_evidence'] == 1
    assert score(label, {'candidates': [{}] * 20 + [a]})['mrr'] == 0
    for change in ({'kind': 'generated'}, {'source_version': 'stale'}, {'page_number': 3}):
        wrong = {'evidence_spans': [{**a['evidence_spans'][0], **change}]}
        assert score(label, {'chunks': [wrong]})['evidence_recall_final'] == 0


def test_numeric_review_tolerance_and_identity():
    label = {'evidence': [], 'expected_outcome': 'answer', 'numeric': [{
        'entity': 'Acme', 'period': 'Q1 2026', 'scope': 'consolidated',
        'unit': 'USD_million', 'value': '42', 'tolerance': '.1'}]}
    claim = {k: v for k, v in label['numeric'][0].items() if k != 'tolerance'}
    assert score(label, {})['numeric_accuracy'] is None
    assert score(label, {'numeric_claims': []})['numeric_accuracy'] == 0
    assert score(label, {'numeric_claims': [{**claim, 'value': '42.1'}]})['numeric_accuracy'] == 1
    for key, value in [('value', '42.1001'), ('entity', 'Other'), ('period', 'Q2 2026'),
                       ('scope', 'segment'), ('unit', 'USD_billion')]:
        assert score(label, {'numeric_claims': [{**claim, key: value}]})['numeric_accuracy'] == 0


def test_citations_resolve_to_retrieved_original_evidence_and_review_is_explicit():
    label = {'evidence': [], 'numeric': [], 'expected_outcome': 'refuse'}
    chunk = {'chunk_id': 'chunk', 'document_id': 'doc', 'source_version': 'hash',
             'evidence_spans': [{'source_version': 'hash', 'kind': 'original', 'text': 'Revenue 42'}]}
    citation = {**chunk, 'provenance_status': 'resolved'}
    result = {'chunks': [chunk], 'citations': [citation], 'invalid_citations': [9], 'outcome': 'refuse'}
    assert score(label, result)['citation_validity'] == .5
    for change in ({'chunk_id': 'missing'}, {'document_id': 'other'}, {'source_version': 'stale'},
                   {'evidence_spans': [{'source_version': 'hash', 'kind': 'generated', 'text': 'Revenue 42'}]}):
        assert score(label, {**result, 'citations': [{**citation, **change}]})['citation_validity'] == 0
    assert score(label, {**result, 'hallucination': {}})['outcome_correctness'] is None
    assert score(label, {**result, 'hallucination': {'n_refuted': 0, 'n_unsupported': 0}})['outcome_correctness'] == 1


def test_latency_and_partial_usage_do_not_invent_zeroes():
    assert latency_summary([None, float('nan'), 0, 10, 20]) == {'p50': 10, 'p95': 19, 'denominator': 3}
    assert latency_summary([]) == {'p50': None, 'p95': None, 'denominator': 0}
    row = {'category': 'fact_finding', 'metrics': {}, 'result': {'cost_usd': 0,
           'usage': {'events': [{'input_tokens': 3, 'output_tokens': 2, 'reasoning_tokens': None, 'cost_usd': 0}]}}}
    group = summarize([row])['all']
    assert group['cost']['mean_query_cost_usd'] == 0
    assert group['usage']['reasoning_tokens'] is None
    group = summarize([row, {**row, 'result': {}}])['all']
    assert group['cost']['mean_query_cost_usd'] is None
    assert group['usage']['receipt_denominator'] == 1
    assert group['usage']['input_tokens'] is None
