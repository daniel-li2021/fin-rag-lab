"""A cited draft cannot exceed its tasks, original quotes or single call ceiling."""
import json
from types import SimpleNamespace

from src.financial.narrative import synthesize_evidence
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
    return [{'task_id': p['task_id'], 'evidence_id': p['evidence_id'], 'text': p['text'], 'quote': p['text']}
            for p in candidates()['passages']]


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
    for change in ({'evidence_id': 'b'}, {'quote': 'Invented exact-looking support text.'}, {'text': 'Revenue grew 99%.'}):
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
