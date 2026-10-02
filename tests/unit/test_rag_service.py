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
                "outcome": "refuse",
            }
        return {
            "answer": f"Mocked answer about {query} [^1].",
            "citations": [chunks[0].chunk_id],
            "refused": False,
            "outcome": "answer",
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


def test_answer_citations_are_distinct_from_retrieved_context_and_keep_numbers(service):
    svc, pdf = service
    svc.ingest_and_index([pdf], require_api_key=False)
    first = next(iter(svc.parent_store.values()))
    chunks = [first, first.model_copy(update={"chunk_id": "source-two"})]
    # Exercise sparse numbering: the answer cites only Source 2.
    svc.query_pipeline.query = lambda q: {'answer': 'Claim [^2]', 'chunks': chunks[:2], 'citations': [chunks[1].chunk_id]}
    result = svc.query('What was net income?', require_api_key=False)
    assert len(result.citations) == 1
    assert result.citations[0]['source_number'] == 2
    assert result.citations[0]['source_version']
    assert result.citations[0]['evidence_spans']
    assert result.citations[0]['provenance_status'] == 'resolved'
    svc.query_pipeline.query = lambda q: {'answer': 'No cited assertion', 'chunks': chunks, 'citations': []}
    result = svc.query('What was net income?', require_api_key=False)
    assert result.citations == []
    assert result.retrieved_contexts


def test_vector_serialization_preserves_provenance_and_marks_legacy():
    from langchain_core.documents import Document as LCDocument
    from src.retrievers import VectorRetriever
    from src.core.models import Document, DocumentBlock
    from src.chunkers import ParentChildChunker
    doc = Document(title='d', source_type='md', source_hash='version', blocks=[DocumentBlock(block_type='paragraph', text='value $5.4 billion', page_number=2)])
    chunk = ParentChildChunker().chunk(doc)[0]
    lc = LCDocument(page_content=chunk.retrieval_text, metadata={'chunk_payload': chunk.model_dump_json()})
    assert VectorRetriever._lc_to_chunk(lc) == chunk
    legacy = VectorRetriever._lc_to_chunk(LCDocument(page_content='old', metadata={'document_id': 'old-id'}))
    assert legacy.document_id == 'old-id'
    assert legacy.source_version is None
    assert legacy.evidence_spans == []


def test_query_usage_and_latency_include_verification_and_exclude_other_requests(service, monkeypatch):
    svc, pdf = service
    svc.ingest_and_index([pdf], require_api_key=False)
    svc.cost_tracker.record_llm('previous_unknown', 'unknown', 99, 99)
    clock = [10.0]
    monkeypatch.setattr('src.services.rag_service.time.perf_counter', lambda: clock[0])
    def query(q):
        svc.cost_tracker.record_embedding('embedding', 'text-embedding-3-small', 100)
        svc.cost_tracker.record_llm('rag_generate', 'gpt-4o-mini', 1000, 500, 200)
        clock[0] += 0.05
        return {'answer': 'unsupported', 'outcome': 'refuse', 'refused': True, 'chunks': [], 'citations': []}
    def verify(answer, chunks):
        svc.cost_tracker.record_llm('hallucination_verify', 'gpt-4o-mini', 1000, 0)
        clock[0] += 0.20
        return {'n_claims': 0, 'n_refuted': 0, 'n_unsupported': 0}
    svc.query_pipeline.query = query
    svc.verify_hallucination = verify
    for _ in range(2):
        result = svc.query('Question', verify_hallucination=True, require_api_key=False)
        assert result.cost_usd == pytest.approx(0.000602)
        assert result.latency_ms == pytest.approx(250)
        assert result.usage['n_calls'] == {'embedding': 1, 'rag_generate': 1, 'hallucination_verify': 1}
        assert 'previous_unknown' not in result.cost_breakdown
        assert result.hallucination is not None  # Refusal prose is verified too.


def test_actual_query_pipeline_copies_usage_context_into_langgraph_workers(service):
    svc, pdf = service
    svc.ingest_and_index([pdf], require_api_key=False)
    def generate(query, chunks):
        svc.cost_tracker.record_llm('rag_generate', 'gpt-4o-mini', 1000, 0)
        return {'answer': 'answer', 'outcome': 'answer', 'citations': []}
    svc.generator.generate = generate
    result = svc.query('What was net income?', require_api_key=False)
    assert result.cost_usd == pytest.approx(0.00015)
    assert result.usage['n_calls']['rag_generate'] == 1


def test_ingest_total_includes_embedding_batches_after_document_captioning(service):
    svc, pdf = service
    ensure = svc._ensure_retrievers
    def tracked_ensure(reset_vector=False):
        ensure(reset_vector)
        index = svc.vector.index
        def tracked_index(chunks):
            svc.cost_tracker.record_embedding('embedding', 'text-embedding-3-small', 7000)
            index(chunks)
        svc.vector.index = tracked_index
    svc._ensure_retrievers = tracked_ensure
    result = svc.ingest_and_index([pdf], require_api_key=False)
    assert result['cost_usd'] == pytest.approx(0.00014)
    assert result['usage']['n_calls'] == {'embedding': 1}
    assert result['documents'][0]['cost_usd'] == 0  # caption receipt, not shared embedding batch
