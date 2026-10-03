"""Real disposable Postgres, retained originals and API; no provider calls."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_persistent import durable
from tests.unit.test_financial_research import fact, plan
from src.api.private_server import build_private_app
from src.financial.models import FinancialPeriod
from src.financial.research import ResearchRequest, run_research
from src.retrievers.postgres import PostgresRetriever


def test_pinned_research_and_metadata_history(durable):
    svc, _, _ = durable
    source = svc.register(kind='text', title='Synthetic reviewed quarterly report',
        metadata={'company_id': 'TEST', 'review_status': 'confirmed', 'publication_date': '2026-04-10'})
    prototype, block = fact()
    svc.ingest_bytes(source['source_id'], block.text.encode())
    selection = {'source_id': str(source['source_id'])}
    snap = svc.registry.research_snapshot('alice', [selection])
    assert len(snap['sources']) == 1
    pin = snap['sources'][0]
    original_block = next(b for b in snap['blocks'][pin.build_id] if b.text == block.text)
    observation = prototype.model_copy(update={'source': pin,
        'evidence': tuple(e.model_copy(update={'block_id': original_block.block_id, 'page_number': None})
                          for e in prototype.evidence)})
    req = ResearchRequest.model_validate({**plan((observation,)).model_dump(mode='json'), 'selections': [selection]})
    first = svc.research(req)
    assert first['outcome'] == 'answer', first
    svc.ingest_bytes(source['source_id'], b'Revenue has changed; replacement not yet reviewed.')
    assert run_research(req, snap) == first
    current = svc.research(req)
    assert current['outcome'] == 'refuse' and not current['citations']
    historical_selection = {**selection, 'version_id': pin.version_id, 'build_id': pin.build_id}
    replay = svc.research({**req.model_dump(mode='json'), 'selections': [historical_selection]})
    assert replay['calculations'] == first['calculations'] and replay['answer'] == first['answer']
    metadata = {'company_id': 'TEST', 'company_name': 'Reviewed Test', 'review_status': 'confirmed',
                'publication_date': '2026-04-10'}
    correction = svc.registry.review_version_metadata('alice', source['source_id'], pin.version_id,
                                                      metadata, 'reviewer', 'Confirmed original header')
    assert correction['revision'] == 1
    corrected = svc.registry.research_snapshot('alice', [historical_selection])
    assert corrected['inventory'][0]['metadata_review_id'] == str(correction['review_id'])
    assert corrected['inventory'][0]['metadata']['company_name'] == 'Reviewed Test'
    pinned_review = {**historical_selection, 'metadata_review_id': str(correction['review_id'])}
    later = svc.registry.review_version_metadata('alice', source['source_id'], pin.version_id,
        {**metadata, 'company_name': 'Later correction'}, 'reviewer', 'Second reviewed correction')
    assert later['revision'] == 2
    assert len(svc.registry.version_metadata_reviews('alice', source['source_id'], pin.version_id)) == 2
    assert svc.registry.research_snapshot('alice', [pinned_review])['inventory'][0]['metadata']['company_name'] == 'Reviewed Test'
    original_version = next(v for v in svc.registry.versions('alice', source['source_id']) if str(v['version_id']) == pin.version_id)
    assert 'company_name' not in original_version['metadata'] or original_version['metadata']['company_name'] is None
    detail = PostgresRetriever(svc.registry, 'alice', svc.embeddings, 'offline', 3,
        {'source_id': str(source['source_id']), 'version_id': pin.version_id, 'company_id': 'TEST'}).retrieve('Revenue')
    assert detail and detail[0].metadata['confirmed_source_metadata']['company_name'] == 'Later correction'
    other = svc.registry.register('bob', {'kind': 'text', 'title': 'Other owner'})
    with pytest.raises(LookupError):
        svc.registry.research_snapshot('alice', [{'source_id': str(other['source_id'])}])
    with pytest.raises(LookupError):
        svc.registry.research_snapshot('alice', [{**selection, 'version_id': str(other['source_id'])}])
    svc.registry.archive('alice', source['source_id'])
    with pytest.raises(LookupError):
        svc.registry.research_snapshot('alice', [historical_selection])


def test_research_api_keeps_auth_and_plan_bounds(durable):
    svc, _, _ = durable
    token = 'offline-secure-token-at-least-24-characters'
    client = TestClient(build_private_app(svc, token))
    assert client.post('/research', json={}).status_code == 401
    client.headers['Authorization'] = 'Bearer ' + token
    source = svc.register(kind='text', title='No snapshot', metadata={'company_id': 'TEST'})
    period = FinancialPeriod(kind='quarter', start=date(2026, 1, 1), end=date(2026, 3, 31), fiscal_label='Q1 2026')
    body = {'question': 'Revenue', 'selections': [{'source_id': str(source['source_id'])}],
        'tasks': [{'task_id': 'revenue', 'company_id': 'TEST', 'metric_id': 'revenue', 'period': period.model_dump(mode='json')}]}
    response = client.post('/research', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['outcome'] == 'refuse'
    assert response.json()['coverage'][0]['status'] == 'source_unavailable'
    assert client.post('/research', json={**body, 'tasks': body['tasks'] * 7}).status_code == 422
    assert client.post('/research', json={**body, 'arbitrary_sql': 'SELECT 1'}).status_code == 422
