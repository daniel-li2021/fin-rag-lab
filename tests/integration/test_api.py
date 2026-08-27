"""
Integration tests for the FastAPI server (adapter over RAGService).

Uses TestClient + a RAGService with NoOpCaptioner and fake retrievers
so we never hit OpenAI.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

from src.api.server import build_app
from src.captioners.vlm_captioner import NoOpCaptioner
from src.observability import CostTracker
from src.pipelines.query import QueryPipeline
from src.retrievers import HybridRetriever
from src.services import RAGService
from tests.unit.test_rag_service import (
    _FakeGenerator,
    _MutableFakeBM25,
    _MutableFakeVector,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from tests.integration.make_test_pdf import make_test_pdf

    # Satisfy RAGService.require_openai_key without calling OpenAI (fakes below)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")

    pdf_path = tmp_path / "test.pdf"
    make_test_pdf(pdf_path)

    svc = RAGService(
        index_dir=tmp_path / "index",
        cache_root=tmp_path / "cache",
        upload_dir=tmp_path / "uploads",
        cost_tracker=CostTracker(),
        enable_langsmith=False,
        captioner=NoOpCaptioner(),
    )

    def fake_ensure(reset_vector: bool = False):
        if svc.vector is None:
            svc.vector = _MutableFakeVector()
            svc.bm25 = _MutableFakeBM25()
            svc.hybrid = HybridRetriever(
                svc.vector, svc.bm25, parent_store=svc.parent_store
            )
            svc.generator = _FakeGenerator()
            svc.query_pipeline = QueryPipeline(svc.hybrid, svc.generator)
        elif reset_vector:
            svc.vector.reset()
        if svc.hybrid is not None:
            svc.hybrid.parent_store = svc.parent_store

    svc._ensure_retrievers = fake_ensure  # type: ignore[method-assign]

    app = build_app(service=svc)
    return TestClient(app), pdf_path


def test_health_endpoint(client):
    test_client, _ = client
    r = test_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "n_documents_indexed" in body
    assert body["strategy"] == "parent_child"


def test_ingest_then_query(client):
    test_client, pdf_path = client

    r = test_client.post("/ingest", json={"path": str(pdf_path)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_blocks"] > 0
    assert body["n_chunks"] > 0

    r2 = test_client.post("/query", json={"question": "What was net income?"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert "answer" in body2
    assert body2["n_chunks_retrieved"] >= 0
    assert "latency_ms" in body2


def test_query_without_ingest_fails(client):
    test_client, _ = client
    r = test_client.post("/query", json={"question": "What?"})
    assert r.status_code == 400


def test_ingest_missing_file_404(client):
    test_client, _ = client
    r = test_client.post("/ingest", json={"path": "/nonexistent.pdf"})
    assert r.status_code == 404
