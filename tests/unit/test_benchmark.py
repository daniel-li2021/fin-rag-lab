import json
from pathlib import Path

import pytest
from src.evaluators.benchmark import load_benchmark, manifest, replay, run_benchmark, score

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
