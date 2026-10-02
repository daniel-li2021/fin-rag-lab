"""Usage, outcomes and request isolation checks; all provider responses are mocked."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from types import SimpleNamespace

import pytest

from src.observability import CostTracker


def test_reasoning_is_part_of_completion_and_zero_usage_is_reported():
    ct = CostTracker()
    raw = {'prompt_tokens': 1000, 'completion_tokens': 500,
           'completion_tokens_details': {'reasoning_tokens': 200}}
    result = SimpleNamespace(response_metadata={'token_usage': raw, 'model_name': 'response-model'})
    assert ct.record_response('generation', 'gpt-4o-mini', result) == pytest.approx(0.00045)
    event = ct.report()['events'][0]
    assert event['output_tokens'] == 500
    assert event['reasoning_tokens'] == 200
    assert event['raw_usage'] == {'usage': raw, 'response_model': 'response-model'}
    zero = SimpleNamespace(response_metadata={}, usage_metadata={'input_tokens': 0, 'output_tokens': 0})
    assert ct.record_response('zero', 'gpt-4o-mini', zero) == 0
    ct.record_response('missing', 'gpt-4o-mini', SimpleNamespace(response_metadata={}))
    assert ct.total is None
    assert ct.report()['priced_subtotal_usd'] == pytest.approx(0.00045)
    assert ct.report()['unknown_calls'] == 1


def test_overlapping_and_nested_receipts_are_isolated_and_restore_on_error():
    ct = CostTracker()
    barrier = Barrier(2)
    def work(tokens):
        with ct.request() as receipt:
            barrier.wait()
            with ct.request() as nested:
                ct.record_llm('generation', 'gpt-4o-mini', tokens, 0)
            assert nested.report()['events'] == receipt.report()['events']
        return receipt.report()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(work, [1000, 2000]))
    assert [r['events'][0]['input_tokens'] for r in receipts] == [1000, 2000]
    assert all(r['n_calls'] == {'generation': 1} for r in receipts)
    assert ct.n_calls['generation'] == 2
    with pytest.raises(RuntimeError):
        with ct.request() as failed:
            ct.record_llm('unknown', 'unpriced', 1, 1)
            raise RuntimeError('failed call')
    assert failed.report()['total_usd'] is None
    with ct.request() as clean:
        ct.record_llm('generation', 'gpt-4o-mini', 1000, 0)
    assert clean.report()['total_usd'] == pytest.approx(0.00015)


def test_embedding_http_usage_is_recorded_only_on_cache_misses(tmp_path, monkeypatch):
    import httpx
    from src.core.cache import make_cached_embeddings
    from src.observability.embeddings import make_tracked_embeddings
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-not-used')
    requests = []
    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        inputs = body['input']
        return httpx.Response(200, json={'object': 'list', 'model': body['model'],
            'data': [{'object': 'embedding', 'index': i, 'embedding': [0.1, 0.2, 0.3]} for i in range(len(inputs))],
            'usage': {'prompt_tokens': 7, 'total_tokens': 7}})
    client_init, async_init = httpx.Client.__init__, httpx.AsyncClient.__init__
    transport = httpx.MockTransport(respond)
    def sync_init(self, *args, **kw):
        client_init(self, *args, transport=transport, **kw)
    def async_init_mock(self, *args, **kw):
        async_init(self, *args, transport=transport, **kw)
    monkeypatch.setattr(httpx.Client, '__init__', sync_init)
    monkeypatch.setattr(httpx.AsyncClient, '__init__', async_init_mock)
    ct = CostTracker()
    base = make_tracked_embeddings('text-embedding-3-small', ct)
    cached = make_cached_embeddings(base, tmp_path, namespace='test')
    with ct.request() as first:
        assert len(cached.embed_documents(['first input', 'second input'])) == 2
    assert first.report()['n_calls'] == {'embedding': 1}
    with ct.request() as hit:
        cached.embed_documents(['first input', 'second input'])
    assert hit.report()['events'] == []
    with ct.request() as query:
        cached.embed_query('question')
    assert query.report()['events'][0]['input_tokens'] == 7
    async def async_check():
        with ct.request() as async_receipt:
            await base.aembed_documents(['async input'])
        return async_receipt.report()
    assert asyncio.run(async_check())['n_calls'] == {'embedding': 1}
    assert len(requests) == 3
    assert ct.report()['events'][0]['raw_usage']['usage'] == {'prompt_tokens': 7, 'total_tokens': 7}


def test_ragas_callback_uses_the_same_usage_contract():
    from src.evaluators.ragas_evaluator import _RagasCostCallback
    ct = CostTracker()
    msg = SimpleNamespace(response_metadata={'token_usage': {'prompt_tokens': 1000,
        'completion_tokens': 500, 'completion_tokens_details': {'reasoning_tokens': 200}}})
    with ct.request() as receipt:
        _RagasCostCallback(ct, 'gpt-4o-mini').on_llm_end(SimpleNamespace(generations=[[SimpleNamespace(message=msg)]]))
    assert receipt.report()['total_usd'] == pytest.approx(0.00045)
