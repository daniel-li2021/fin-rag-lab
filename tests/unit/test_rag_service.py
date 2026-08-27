"""
Unit tests for RAGService — no OpenAI calls.

Uses NoOpCaptioner + fake vector/BM25-compatible stubs so ingest/index/query
work offline against the synthetic test PDF.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.core.models import DocumentChunk
from src.captioners.vlm_captioner import NoOpCaptioner
from src.observability import CostTracker
from src.services.rag_service import RAGService
from src.pipelines.query import QueryPipeline
from src.retrievers import HybridRetriever


class _MutableFakeVector:
    name = "fake_vector"

    def __init__(self):
        self.chunks: list[DocumentChunk] = []

    def index(self, chunks):
        self.chunks.extend(chunks)

    def retrieve(self, query, k=5):
        return self.chunks[:k]

    def search_with_scores(self, query, k=10):
        return [(c, 1.0 / (i + 1)) for i, c in enumerate(self.chunks[:k])]

    def reset(self):
        self.chunks = []


class _MutableFakeBM25:
    name = "fake_bm25"

    def __init__(self):
        self.chunks: list[DocumentChunk] = []

    def index(self, chunks):
        self.chunks = list(chunks)

    def retrieve(self, query, k=5):
        return self.chunks[:k]

    def search_with_scores(self, query, k=10):
        return [(c, 1.0 / (i + 1)) for i, c in enumerate(self.chunks[:k])]


class _FakeGenerator:
    name = "fake_generator"

    def generate(self, query, chunks):
        if not chunks:
            return {
                "answer": "I could not find any relevant information.",
                "citations": [],
                "refused": True,
            }
        return {
            "answer": f"Mocked answer about {query} [^1].",
            "citations": [chunks[0].chunk_id],
            "refused": False,
            "n_sources_used": 1,
        }


@pytest.fixture
def pdf_path(tmp_path):
    from tests.integration.make_test_pdf import make_test_pdf

    path = tmp_path / "earnings.pdf"
    make_test_pdf(path)
    return path


@pytest.fixture
def service(tmp_path, pdf_path, monkeypatch):
    """RAGService with NoOp captioner and fake retrievers (no API key)."""
    monkeypatch.chdir(tmp_path)
    upload = tmp_path / "uploads"
    upload.mkdir()
    # copy pdf into upload dir for list_available_pdfs
    dest = upload / pdf_path.name
    dest.write_bytes(pdf_path.read_bytes())

    svc = RAGService(
        index_dir=tmp_path / "index",
        cache_root=tmp_path / "cache",
        upload_dir=upload,
        cost_tracker=CostTracker(),
        enable_langsmith=False,
        captioner=NoOpCaptioner(),
    )

    # Patch _ensure_retrievers to avoid Chroma / OpenAI embeddings
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
    return svc, dest


def test_ingest_and_index_parent_child(service):
    svc, pdf = service
    result = svc.ingest_and_index([pdf], reset=True, verbose=False, require_api_key=False)

    assert result["n_documents"] == 1
    assert result["n_children"] > 0
    assert result["n_parents"] > 0
    assert svc.is_ready()
    assert (svc.index_dir / "index_meta.json").exists()
    assert (svc.index_dir / "parents.pkl").exists()
    assert (svc.index_dir / "children.pkl").exists()

    status = svc.status()
    assert status.strategy == "parent_child"
    assert status.n_children == result["n_children"]


def test_save_and_load_index(service, tmp_path):
    svc, pdf = service
    svc.ingest_and_index([pdf], reset=True, require_api_key=False)

    # New service instance loads the same index
    svc2 = RAGService(
        index_dir=svc.index_dir,
        cache_root=tmp_path / "cache2",
        enable_langsmith=False,
        captioner=NoOpCaptioner(),
    )

    def fake_ensure(reset_vector: bool = False):
        if svc2.vector is None:
            svc2.vector = _MutableFakeVector()
            svc2.bm25 = _MutableFakeBM25()
            svc2.hybrid = HybridRetriever(
                svc2.vector, svc2.bm25, parent_store=svc2.parent_store
            )
            svc2.generator = _FakeGenerator()
            svc2.query_pipeline = QueryPipeline(svc2.hybrid, svc2.generator)
        if svc2.hybrid is not None:
            svc2.hybrid.parent_store = svc2.parent_store

    svc2._ensure_retrievers = fake_ensure  # type: ignore[method-assign]
    assert svc2.load_index() is True
    assert svc2.is_ready()
    assert svc2.status().n_children == svc.status().n_children
    # BM25 rebuilt from children
    assert len(svc2.bm25.chunks) == svc2.status().n_children


def test_query_returns_answer_and_trace(service):
    svc, pdf = service
    svc.ingest_and_index([pdf], reset=True, require_api_key=False)

    result = svc.query("What was net income?", require_api_key=False)
    assert result.answer
    assert result.latency_ms >= 0
    assert isinstance(result.stages, list)
    assert len(result.stages) >= 1
    assert result.n_chunks_retrieved >= 1
    assert result.hallucination is None  # default offline path


def test_query_without_index_raises(tmp_path):
    svc = RAGService(
        index_dir=tmp_path / "empty_index",
        cache_root=tmp_path / "cache",
        enable_langsmith=False,
        captioner=NoOpCaptioner(),
    )
    with pytest.raises(RuntimeError, match="No index"):
        svc.query("Anything?", require_api_key=False)


def test_list_available_pdfs(service):
    svc, _ = service
    pdfs = svc.list_available_pdfs()
    assert len(pdfs) == 1
    assert pdfs[0].suffix == ".pdf"


def test_hybrid_uses_parent_store(service):
    svc, pdf = service
    svc.ingest_and_index([pdf], reset=True, require_api_key=False)
    assert svc.hybrid is not None
    assert len(svc.hybrid.parent_store) == svc.status().n_parents
    # Children have parent pointers
    assert any(c.parent_chunk_id for c in svc.children)


def test_reset_false_still_clean_rebuild(service):
    """Partial append is unsupported — reset=False must still rebuild cleanly."""
    svc, pdf = service
    svc.ingest_and_index([pdf], reset=True, require_api_key=False)
    n1 = svc.status().n_children
    # Second call with reset=False must not duplicate children in-memory
    svc.ingest_and_index([pdf], reset=False, require_api_key=False)
    assert svc.status().n_children == n1
    assert svc.is_ready()


def test_load_index_rejects_incomplete(tmp_path):
    svc = RAGService(
        index_dir=tmp_path / "index",
        cache_root=tmp_path / "cache",
        enable_langsmith=False,
        captioner=NoOpCaptioner(),
    )
    (tmp_path / "index").mkdir()
    (tmp_path / "index" / "index_meta.json").write_text("{}")
    assert svc.load_index() is False


def test_per_document_cost_is_delta(service):
    svc, pdf = service
    result = svc.ingest_and_index([pdf], reset=True, require_api_key=False)
    # Single doc: document cost should equal reported ingest cost
    assert result["documents"][0]["cost_usd"] == pytest.approx(result["cost_usd"])
