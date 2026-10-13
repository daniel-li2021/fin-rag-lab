"""A cited draft cannot exceed its tasks, original quotes or single call ceiling."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from src.financial.narrative import synthesize_evidence, original_excerpts
from src.observability import CostTracker


def candidates():
    return {'run_id': 'original', 'request': {'question': 'Issuer reasons', 'tasks': [
        {'task_id': 'a', 'company_id': 'AMD'}, {'task_id': 'b', 'company_id': 'TSLA'}]},
        'coverage': [{'task_id': t, 'status': 'binding_unverified'} for t in ('a', 'b')],
        'passages': [{'task_id': t, 'evidence_id': t, 'source': {'company_id': c}, 'block_id': t,
                      'page_number': 4, 'text': text} for t,c,text in [
            ('a', 'AMD', 'Revenue grew due to strong product demand.'),
            ('b', 'TSLA', 'Revenue declined due to fewer vehicle deliveries.')]],
        'outcome': 'qualified_answer', 'usage': {'planner_calls': 0, 'generator_calls': 0}}


class Model:
    def __init__(self, claims):
        self.claims, self.calls = claims, 0
    def invoke(self, messages):
        self.calls += 1
        assert 'untrusted evidence' in messages[0].content
        return SimpleNamespace(content=json.dumps({'claims': self.claims}),
            response_metadata={'token_usage': {'prompt_tokens': 100, 'completion_tokens': 40}})


def claims():
    return [{'task_id': p['task_id'], 'excerpt_id': f'e{n+1}', 'text': p['text']}
            for n,p in enumerate(candidates()['passages'])]


def test_narrative_draft_preserves_original_task_quotes_and_records_usage():
    model = Model(claims())
    tracker = CostTracker(pricing={'test': {'input': .01, 'output': .02}})
    result = synthesize_evidence(candidates(), tracker, llm=model, model='test')
    assert result['outcome'] == 'qualified_answer' and model.calls == 1
    assert len(result['claims']) == 2 and result['usage']['generator_calls'] == 1
    assert result['usage']['events'][0]['input_tokens'] == 100
    assert result['synthesis_review_status'] == 'unreviewed'
    assert all(c['char_start'] == 0 and c['review_status'] == 'unreviewed_generated_claim' for c in result['claims'])
    assert all(c['status'] == 'binding_unverified' for c in result['coverage'])


def test_cross_task_or_invented_numeric_claims_cannot_complete_synthesis():
    for change in ({'excerpt_id': 'e2'}, {'excerpt_id': 'invented:0'}, {'text': 'Revenue grew 99%.'}):
        values = claims()
        values[0].update(change)
        result = synthesize_evidence(candidates(), CostTracker(), llm=Model(values), model='test')
        assert result['outcome'] == 'refuse' and not result['claims'] and result['synthesis_errors']
    result = synthesize_evidence(candidates(), CostTracker(), llm=Model(claims()[:1]), model='test')
    assert result['outcome'] == 'refuse' and not result['claims']


def test_missing_required_source_withholds_model_call():
    result = candidates()
    result['coverage'][0]['status'] = 'source_absent'
    model = Model(claims())
    result = synthesize_evidence(result, CostTracker(), llm=model, model='test')
    assert result['outcome'] == 'refuse' and model.calls == 0


def test_provider_failure_retains_candidates_and_unknown_usage_without_private_errors():
    class Broken:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            raise TimeoutError('private provider credentials and request content')
    model = Broken()
    original = candidates()
    original['citations'] = {p['evidence_id']: p for p in original['passages']}
    result = synthesize_evidence(original, CostTracker(), llm=model, model='test')
    assert model.calls == 1 and result['outcome'] == 'qualified_answer'
    assert result['passages'] == original['passages'] and result['citations'] == original['citations']
    assert not result['claims'] and result['synthesis_review_status'] == 'unavailable'
    assert result['usage']['unknown_calls'] == 1 and result['usage']['total_usd'] is None
    assert result['usage']['generator_calls'] == 1
    assert result['synthesis_errors'] == ['provider_failure:TimeoutError']
    assert 'private provider' not in json.dumps(result)


def test_one_original_block_can_support_two_required_narrative_tasks():
    original = candidates()
    for passage in original['passages']:
        passage.update(evidence_id='same-original', text='Revenue grew due to demand and margins grew due to mix.',
                       source={'company_id': 'AMD'})
    original['request']['tasks'][1]['company_id'] = 'AMD'
    draft = [{'task_id': 'a', 'excerpt_id': 'e1', 'text': 'Revenue grew due to demand.'},
             {'task_id': 'b', 'excerpt_id': 'e2', 'text': 'Margins grew due to mix.'}]
    result = synthesize_evidence(original, CostTracker(), llm=Model(draft), model='test')
    assert result['outcome'] == 'qualified_answer'
    assert {c['task_id'] for c in result['claims']} == {'a', 'b'}
    assert all(c['evidence_id'] == 'same-original' for c in result['claims'])


def test_excerpt_selection_retains_exact_bounded_original_spans():
    result = candidates()
    text = ('Repeated original sentence. ' * 70) + 'Final sentence.'
    result['passages'][0]['text'] = text
    excerpts = original_excerpts({p['evidence_id']: p for p in result['passages']})
    chosen = [e for e in excerpts.values() if e['task_id'] == 'a']
    assert len(chosen) > 1 and all(20 <= len(e['quote']) <= 700 for e in chosen)
    assert all(text[e['char_start']:e['char_end']] == e['quote'] for e in chosen)
    draft = [{'task_id':'a','excerpt_id':chosen[1]['excerpt_id'],'text':'Repeated original sentence.'},
             {'task_id':'b','excerpt_id':next(e['excerpt_id'] for e in excerpts.values() if e['task_id']=='b'),
              'text':result['passages'][1]['text']}]
    answer = synthesize_evidence(result, CostTracker(), llm=Model(draft), model='test')
    assert answer['outcome'] == 'qualified_answer' and answer['claims'][0]['char_start'] > 0


@pytest.mark.parametrize('case_id', ['dev-08', 'dev-15', 'dev-16'])
def test_saved_authentic_drafts_use_period_labels_in_integrated_synthesis(case_id, monkeypatch):
    from src.core import config
    from src.financial.research import _canonical
    import hashlib
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / 'docs/benchmarks/20261003-product-development/capture-v4/results.jsonl').read_text().splitlines()]
    previous = next(row['result'] for row in rows if row['case_id'] == case_id)
    excerpts = original_excerpts({p['evidence_id']: p for p in previous['passages']})
    draft = []
    for claim in previous['claims']:
        excerpt = next(e for e in excerpts.values() if all(e[k] == claim[k]
                       for k in ('task_id', 'evidence_id', 'quote', 'char_start', 'char_end')))
        draft.append({'task_id': claim['task_id'], 'excerpt_id': excerpt['excerpt_id'], 'text': claim['text']})
    def forbidden(*args, **kwargs):
        raise AssertionError('Saved draft validation must not construct a provider client')
    monkeypatch.setattr(config, 'make_chat_llm', forbidden)
    result = synthesize_evidence(previous, CostTracker(), llm=Model(draft), model='saved')
    assert result['claims'] == previous['claims']
    assert result['synthesis_review_status'] == previous['synthesis_review_status'] == 'unreviewed'
    for task in previous['request']['tasks']:
        assert f"{task['company_id']} / {task['document_period_label']}:" in result['answer']
    assert result['run_id'] == hashlib.sha256(_canonical({k:v for k,v in result.items() if k != 'run_id'}).encode()).hexdigest()
