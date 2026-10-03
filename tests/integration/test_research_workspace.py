"""Saved research and reviewed facts survive updates; all data and embeddings are synthetic."""
import pytest
from fastapi.testclient import TestClient

from tests.integration.test_persistent import durable
from tests.unit.test_financial_research import fact, plan
from src.api.private_server import build_private_app
from src.financial.research import ResearchRequest


def reviewed_source(svc, value="12"):
    source = svc.register(kind='text', title='Synthetic test report', metadata={
        'company_id': 'TEST', 'company_name': 'Test', 'review_status': 'confirmed',
        'publication_date': '2026-04-10', 'period_label': 'Q1 2026'})
    prototype, block = fact(value=value)
    svc.ingest_bytes(source['source_id'], block.text.encode())
    selection = {'source_id': str(source['source_id'])}
    snap = svc.registry.research_snapshot(svc.owner, [selection])
    pin = snap['sources'][0]
    original = next(b for b in snap['blocks'][pin.build_id] if b.text == block.text)
    observation = prototype.model_copy(update={'source': pin,
        'evidence': tuple(e.model_copy(update={'block_id': original.block_id, 'page_number': None}) for e in prototype.evidence)})
    request = ResearchRequest.model_validate({**plan((observation,)).model_dump(mode='json'), 'selections': [selection], 'observations': []})
    return source, observation, request


def test_immutable_observations_collections_saved_history_and_rerun(durable):
    svc, _, _ = durable
    source, observation, request = reviewed_source(svc)
    assert svc.registry.save_observation(svc.owner, observation) == observation.model_dump(mode='json')
    assert svc.registry.save_observation(svc.owner, observation) == observation.model_dump(mode='json')
    with pytest.raises(ValueError, match='immutable'):
        svc.registry.save_observation(svc.owner, observation.model_copy(update={'review_revision': 'new-review'}))
    with pytest.raises(LookupError):
        svc.registry.save_observation('bob', observation)
    collection = svc.registry.create_collection(svc.owner, {'name': 'My watchlist', 'kind': 'watchlist',
                                                           'source_ids': [str(source['source_id'])]})
    assert len(svc.registry.collections(svc.owner)) == 1
    assert svc.registry.collections('bob') == []
    resolved = svc.research_question('show GAAP consolidated revenue for Test in Q1 2026',
                                    collection_id=collection['collection_id'], save=True)
    assert resolved['outcome'] == 'answer', resolved
    assert resolved['usage']['generator_calls'] == 0
    first = svc.registry.research_run(svc.owner, resolved['run_id'])['payload']
    assert first == resolved and not svc.registry.research_changes(svc.owner, first)['potentially_stale']
    with pytest.raises(LookupError):
        svc.registry.research_run('bob', first['run_id'])
    unchanged = svc.rerun_research(first['run_id'])
    assert unchanged['result']['run_id'] != first['run_id']
    assert unchanged['result']['answer'] == first['answer']
    assert unchanged['result']['execution']['parent_run_id'] == first['run_id']
    svc.ingest_bytes(source['source_id'], b'Revenue now needs a new reviewed binding.')
    assert svc.registry.research_changes(svc.owner, first)['potentially_stale']
    assert svc.registry.research_run(svc.owner, first['run_id'])['payload'] == first
    rerun = svc.rerun_research(first['run_id'])
    assert rerun['result']['outcome'] == 'refuse' and rerun['diff']['answer_changed']
    assert not rerun['result']['citations']
    assert len(svc.registry.research_runs(svc.owner)) == 3
    svc.registry.archive(svc.owner, source['source_id'])
    assert svc.registry.research_run(svc.owner, first['run_id'])['payload'] == first
    with pytest.raises(LookupError):
        svc.rerun_research(first['run_id'])


def test_workspace_api_and_unknown_company_fail_closed(durable):
    svc, _, _ = durable
    source, observation, request = reviewed_source(svc)
    client = TestClient(build_private_app(svc, 'offline-token-at-least-24-characters'))
    assert client.get('/research/runs').status_code == 401
    client.headers['Authorization'] = 'Bearer offline-token-at-least-24-characters'
    assert client.post('/research/observations', json=observation.model_dump(mode='json')).status_code == 200
    body = {'question': 'compare GAAP consolidated revenue for Test and Unknown in Q1 2026',
            'selections': [{'source_id': str(source['source_id'])}]}
    result = client.post('/research/questions', json=body).json()
    assert result['outcome'] == 'refuse' and not result['citations']
    saved = client.post('/research/runs', json=request.model_dump(mode='json'))
    assert saved.status_code == 200, saved.text
    run_id = saved.json()['run_id']
    assert client.get('/research/runs/' + run_id).json()['payload'] == saved.json()
    assert client.post('/research/runs/' + run_id + '/rerun').status_code == 200
    assert client.get('/research/runs/missing').status_code == 404


def test_failed_refresh_and_two_company_evidence_keep_last_good(durable):
    svc, _, _ = durable
    source, observation, request = reviewed_source(svc)
    first = svc.research({**request.model_dump(mode='json'), 'observations': [observation.model_dump(mode='json')]}, save=True)
    class Broken:
        def embed_documents(self, texts):
            raise RuntimeError('Synthetic failed refresh')
    original_embeddings = svc.embeddings
    svc.embeddings = Broken()
    with pytest.raises(RuntimeError):
        svc.ingest_bytes(source['source_id'], b'New content which fails before publication.')
    svc.embeddings = original_embeddings
    changes = svc.registry.research_changes(svc.owner, first)
    assert not changes['potentially_stale'] and changes['changes'][0]['refresh_error']
    assert svc.registry.research_run(svc.owner, first['run_id'])['payload'] == first
    assert svc.rerun_research(first['run_id'])['result']['answer'] == first['answer']
    a = svc.register(kind='text', title='Risks A', metadata={'company_id': 'A', 'review_status': 'confirmed'})
    b = svc.register(kind='text', title='Risks B', metadata={'company_id': 'B', 'review_status': 'confirmed'})
    svc.ingest_bytes(a['source_id'], b'Credit risk and market risk.')
    svc.ingest_bytes(b['source_id'], b'Supply risk and export restrictions.')
    result = svc.research_evidence({'question': 'Review both risk sources',
        'selections': [{'source_id': str(s['source_id'])} for s in (a, b)],
        'tasks': [{'task_id': 'a', 'company_id': 'A', 'query': 'risk'}, {'task_id': 'b', 'company_id': 'B', 'query': 'risk'}]}, save=True)
    assert {p['source']['company_id'] for p in result['passages']} == {'A', 'B'}
    assert result['usage']['generator_calls'] == 0
    assert svc.rerun_research(result['run_id'])['result']['passages'] == result['passages']


def test_streamlit_workspace_renders_and_runs_reviewed_lookup(durable, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import app.research_workspace as workspace
    svc, _, _ = durable
    source, observation, _ = reviewed_source(svc)
    svc.registry.save_observation(svc.owner, observation)
    monkeypatch.setattr(workspace, '_test_service', svc, raising=False)
    app = AppTest.from_string('from app.research_workspace import render_research, _test_service\nrender_research(_test_service)').run()
    assert not app.exception
    app.multiselect[0].set_value([str(source['source_id'])]).run()
    app.multiselect[1].set_value(['TEST'])
    next(t for t in app.text_input if t.label == 'Reporting period').set_value('Q1 2026')
    next(b for b in app.button if b.label == 'Run and save research').click().run()
    assert not app.exception
    assert app.session_state['research_result']['outcome'] == 'answer'
    assert len(svc.registry.research_runs(svc.owner)) == 1


def test_task_scoped_cards_keep_conflicts_and_ignore_large_unrelated_library(durable):
    from psycopg.types.json import Jsonb
    from src.storage.registry import config_hash
    svc, _, _ = durable
    source, observation, request = reviewed_source(svc)
    svc.registry.save_observation(svc.owner, observation)
    # A large authentic-style history must not truncate the requested card.
    with svc.registry.connect() as db:
        for i in range(120):
            payload = {**observation.model_dump(mode='json'), 'observation_id': f'unrelated-{i}', 'metric_id': 'other'}
            db.execute('INSERT INTO financial_observations(owner_id,observation_id,build_id,payload,payload_hash) VALUES(%s,%s,%s,%s,%s)',
                       (svc.owner, payload['observation_id'], observation.source.build_id, Jsonb(payload), config_hash(payload)))
    assert svc.research(request)['outcome'] == 'answer'
    assert svc.research_question('show GAAP consolidated revenue for Test in Q1 2026',
                                selections=[{'source_id': str(source['source_id'])}])['outcome'] == 'answer'
    assert svc.registry.observations('bob', [observation.source.build_id], [{'metric_id': 'revenue'}]) == []
    # Conflicts are never removed by task scoping, even across fiscal label aliases.
    other_source, conflicting, _ = reviewed_source(svc, value='13')
    svc.registry.save_observation(svc.owner, conflicting.model_copy(update={'observation_id': 'conflict',
        'period': conflicting.period.model_copy(update={'fiscal_label': 'Q1 2026 alternate'})}))
    conflicted_request = {**request.model_dump(mode='json'), 'selections': [
        {'source_id': str(s['source_id'])} for s in (source, other_source)]}
    assert svc.research(conflicted_request)['coverage'][0]['status'] == 'conflicting'
    with pytest.raises(ValueError, match='immutable'):
        svc.research({**request.model_dump(mode='json'), 'observations': [
            observation.model_copy(update={'metric_id': 'other'}).model_dump(mode='json')]})
    with svc.registry.connect() as db:
        db.execute("UPDATE financial_observations SET payload=jsonb_set(payload, '{metric_id}', '\"revenue\"') WHERE owner_id=%s AND observation_id LIKE 'unrelated-%%'", (svc.owner,))
    with pytest.raises(ValueError, match='exceeds 100'):
        svc.research(request)


def test_safe_question_outcomes_save_reopen_and_rerun(durable):
    svc, _, _ = durable
    source, observation, _ = reviewed_source(svc)
    svc.registry.save_observation(svc.owner, observation)
    for question, outcome in [('What is revenue?', 'clarify'),
        ('compare GAAP consolidated revenue for Test and Unknown in Q1 2026', 'refuse')]:
        result = svc.research_question(question, selections=[{'source_id': str(source['source_id'])}], save=True)
        assert result['outcome'] == outcome
        assert svc.registry.research_run(svc.owner, result['run_id'])['payload'] == result
        assert not svc.registry.research_changes(svc.owner, result)['potentially_stale']
        rerun = svc.rerun_research(result['run_id'])['result']
        assert rerun['outcome'] == outcome and rerun['execution']['parent_run_id'] == result['run_id']
        assert not rerun['citations']
    assert len(svc.registry.research_runs(svc.owner)) == 4
