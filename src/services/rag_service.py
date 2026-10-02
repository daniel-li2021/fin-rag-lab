"""
RAGService — shared orchestration for the local application.

Wraps existing IngestionPipeline / QueryPipeline / ParentChild chunking /
HybridRetriever without rewriting the RAG core. Notebook 05's improved
strategy is the default:

  ParentChildChunker(parent=800, child=150)
  → index children in Vector + BM25
  → HybridRetriever with parent_store expansion at retrieval time
  → QueryPipeline (LangGraph)

Offline evaluation (Ragas) and optional HallucinationDetector stay separate
from the normal online query path.

Index layout under ``index_dir``:
  chroma/          — Chroma vector store (children)
  parents.pkl      — parent chunks for expansion
  children.pkl     — children for BM25 rebuild on load
  index_meta.json  — document list + strategy knobs
"""
from __future__ import annotations

import json
import pickle
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.core.cache import CacheBundle
from src.core.config import settings, configure_langsmith
from src.core.models import DocumentChunk
from src.observability import CostTracker
from src.pipelines import IngestionPipeline, QueryPipeline
from src.chunkers import ParentChildChunker
from src.retrievers import VectorRetriever, BM25Retriever, HybridRetriever
from src.generators import RAGGenerator


DEFAULT_PARENT_SIZE = 800
DEFAULT_CHILD_SIZE = 150
DEFAULT_COLLECTION = "fin_rag_app"
META_FILENAME = "index_meta.json"
PARENTS_FILENAME = "parents.pkl"
CHILDREN_FILENAME = "children.pkl"
CHROMA_SUBDIR = "chroma"


def _resolve_path(path: str | Path | None, default_relative: str) -> Path:
    """Resolve a path: absolute stays; relative is anchored at repo_root."""
    raw = Path(path) if path is not None else Path(default_relative)
    if raw.is_absolute():
        return raw
    return (settings.repo_root / raw).resolve()


@dataclass
class IndexedDocument:
    document_id: str
    title: str
    source_path: str
    n_pages: int
    n_blocks: int
    n_parents: int
    n_children: int
    cache_hit: bool = False
    cost_usd: Optional[float] = 0.0


@dataclass
class IndexStatus:
    ready: bool
    index_dir: str
    n_documents: int = 0
    n_parents: int = 0
    n_children: int = 0
    documents: list[dict[str, Any]] = field(default_factory=list)
    strategy: str = "parent_child"
    parent_size: int = DEFAULT_PARENT_SIZE
    child_size: int = DEFAULT_CHILD_SIZE
    openai_key_set: bool = False


@dataclass
class QueryResult:
    query: str
    answer: str
    citations: list[dict[str, Any]]
    chunks: list[DocumentChunk]
    refused: bool
    query_type: Optional[str]
    stages: list[str]
    latency_ms: float
    n_chunks_retrieved: int
    cost_usd: Optional[float]
    cost_breakdown: dict[str, Optional[float]]
    hallucination: Optional[dict[str, Any]] = None
    retrieved_contexts: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[DocumentChunk] = field(default_factory=list)
    invalid_citations: list[Any] = field(default_factory=list)
    outcome: Optional[str] = None
    usage: dict[str, Any] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)
    retrieval_latency_ms: float = 0.0

    def to_display_dict(self) -> dict[str, Any]:
        """JSON-friendly view for UIs (serializes chunks for optional debug panels)."""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": self.citations,
            "retrieved_contexts": self.retrieved_contexts,
            "invalid_citations": self.invalid_citations,
            "refused": self.refused,
            "outcome": self.outcome,
            "usage": self.usage,
            "configuration": self.configuration,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "query_type": self.query_type,
            "stages": self.stages,
            "latency_ms": self.latency_ms,
            "n_chunks_retrieved": self.n_chunks_retrieved,
            "cost_usd": self.cost_usd,
            "cost_breakdown": self.cost_breakdown,
            "hallucination": self.hallucination,
            "retrieved_context": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page_number": c.page_number,
                    "heading_path": list(c.heading_path),
                    "parent_chunk_id": c.parent_chunk_id,
                    "text": c.text,
                }
                for c in self.chunks
            ],
        }


class RAGService:
    """Single entry point for ingest / index / query / evaluate."""

    def __init__(
        self,
        index_dir: str | Path | None = None,
        cache_root: str | Path | None = None,
        upload_dir: str | Path | None = None,
        parent_size: int = DEFAULT_PARENT_SIZE,
        child_size: int = DEFAULT_CHILD_SIZE,
        collection: str = DEFAULT_COLLECTION,
        cost_tracker: Optional[CostTracker] = None,
        enable_langsmith: bool = True,
        captioner=None,
        require_api_key: bool = False,
    ):
        self.index_dir = _resolve_path(index_dir, "index")
        self.cache_root = _resolve_path(cache_root, "cache")
        self.upload_dir = _resolve_path(
            upload_dir if upload_dir is not None else settings.upload_dir,
            "data/uploads",
        )
        self.parent_size = parent_size
        self.child_size = child_size
        self.collection = collection

        if enable_langsmith:
            configure_langsmith()

        if require_api_key:
            self.require_openai_key()

        self.cost_tracker = cost_tracker or CostTracker()
        self.cache = CacheBundle.from_root(
            self.cache_root, enabled=settings.cache_enabled_default
        )
        self.ingestion = IngestionPipeline(
            cache=self.cache,
            cost_tracker=self.cost_tracker,
            cache_root=self.cache_root,
            captioner=captioner,
        )
        self.chunker = ParentChildChunker(
            parent_size=parent_size, child_size=child_size
        )

        self.vector: Optional[VectorRetriever] = None
        self.bm25: Optional[BM25Retriever] = None
        self.hybrid: Optional[HybridRetriever] = None
        self.generator: Optional[RAGGenerator] = None
        self.query_pipeline: Optional[QueryPipeline] = None

        self.parent_store: dict[str, DocumentChunk] = {}
        self.children: list[DocumentChunk] = []
        self.documents: list[IndexedDocument] = []
        self._ready = False

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    @property
    def chroma_dir(self) -> Path:
        return self.index_dir / CHROMA_SUBDIR

    @property
    def meta_path(self) -> Path:
        return self.index_dir / META_FILENAME

    @property
    def parents_path(self) -> Path:
        return self.index_dir / PARENTS_FILENAME

    @property
    def children_path(self) -> Path:
        return self.index_dir / CHILDREN_FILENAME

    # ------------------------------------------------------------------
    # Status / discovery / guards
    # ------------------------------------------------------------------
    @staticmethod
    def require_openai_key() -> None:
        if not settings.has_openai_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
                "or export OPENAI_API_KEY before running."
            )

    def is_ready(self) -> bool:
        return self._ready and self.query_pipeline is not None

    def index_files_present(self) -> bool:
        return (
            self.meta_path.exists()
            and self.parents_path.exists()
            and self.children_path.exists()
        )

    def status(self) -> IndexStatus:
        return IndexStatus(
            ready=self.is_ready(),
            index_dir=str(self.index_dir.resolve()),
            n_documents=len(self.documents),
            n_parents=len(self.parent_store),
            n_children=len(self.children),
            documents=[asdict(d) for d in self.documents],
            strategy="parent_child",
            parent_size=self.parent_size,
            child_size=self.child_size,
            openai_key_set=settings.has_openai_key,
        )

    def list_available_pdfs(self) -> list[Path]:
        if not self.upload_dir.exists():
            return []
        return sorted(self.upload_dir.glob("*.pdf"))

    def cost_report(self) -> dict[str, Any]:
        return self.cost_tracker.report()

    # ------------------------------------------------------------------
    # Index build / load
    # ------------------------------------------------------------------
    def _ensure_retrievers(self, reset_vector: bool = False) -> None:
        """Lazily construct retrievers + generator + query pipeline."""
        if self.vector is None:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            self.vector = VectorRetriever(
                persist_dir=self.chroma_dir,
                collection=self.collection,
                embeddings_cache_dir=self.cache.embeddings_dir,
                cost_tracker=self.cost_tracker,
            )
            self.bm25 = BM25Retriever()
            self.hybrid = HybridRetriever(
                self.vector, self.bm25, parent_store=self.parent_store
            )
            self.generator = RAGGenerator(cost_tracker=self.cost_tracker)
            self.query_pipeline = QueryPipeline(
                self.hybrid, self.generator, cost_tracker=self.cost_tracker
            )
        elif reset_vector:
            self.vector.reset()

        if self.hybrid is not None:
            self.hybrid.parent_store = self.parent_store

    def ingest_and_index(
        self,
        sources: list[str | Path],
        *,
        max_pages: Optional[int] = None,
        page_range: Optional[tuple[int, int]] = None,
        reset: bool = True,
        verbose: bool = False,
        require_api_key: bool = True,
    ) -> dict[str, Any]:
        """
        Ingest PDFs, parent-child chunk, and rebuild the hybrid index.

        Always performs a **clean rebuild** from ``sources``. The ``reset``
        flag is kept for API compatibility; ``reset=False`` is treated as
        ``True`` with a warning because partial append into Chroma without
        updating parent_store/BM25 produces a corrupt index.
        """
        if require_api_key:
            self.require_openai_key()

        paths = [Path(p).resolve() for p in sources]
        for p in paths:
            if not p.exists():
                raise FileNotFoundError(f"PDF not found: {p}")
            if p.suffix.lower() != ".pdf":
                raise ValueError(f"Expected a PDF file, got: {p}")

        if not reset:
            if verbose:
                print(
                    "Note: partial append is not supported; "
                    "performing a clean rebuild from the selected PDFs."
                )
            reset = True

        with self.cost_tracker.request() as receipt:
            t0 = time.perf_counter()
            self._reset_index_state()
            self._ensure_retrievers(reset_vector=True)

            new_docs: list[IndexedDocument] = []
            all_parents: list[DocumentChunk] = []
            all_children: list[DocumentChunk] = []

            for path in paths:
                if verbose:
                    print(f"Ingesting {path.name}...")
                report = self.ingestion.ingest(
                    path, max_pages=max_pages, page_range=page_range, verbose=verbose
                )
                doc_cost = report.total_cost_usd

                parents, children = self.chunker.chunk_with_parents(report.document)
                all_parents.extend(parents)
                all_children.extend(children)

                new_docs.append(
                    IndexedDocument(
                        document_id=report.document.document_id,
                        title=report.document.title,
                        source_path=str(path.resolve()),
                        n_pages=report.document.n_pages,
                        n_blocks=len(report.document.blocks),
                        n_parents=len(parents),
                        n_children=len(children),
                        cache_hit=report.parse_cache_hit,
                        cost_usd=doc_cost,
                    )
                )
                if verbose:
                    print(
                        f"  → {len(parents)} parents / {len(children)} children "
                        f"(cache_hit={report.parse_cache_hit}, cost={doc_cost})"
                    )

            if not all_children:
                raise RuntimeError(
                    "Ingestion produced 0 chunks. Check that the PDFs contain extractable text."
                )

            self.parent_store = {p.chunk_id: p for p in all_parents}
            self.children = list(all_children)
            self.documents = new_docs
            assert self.hybrid is not None
            self.hybrid.parent_store = self.parent_store
            self.hybrid.index(self.children)

            self._save_index()
            self._ready = True

            wall = time.perf_counter() - t0
            return {
                "n_documents": len(self.documents),
                "n_parents": len(self.parent_store),
                "n_children": len(self.children),
                "documents": [asdict(d) for d in self.documents],
                "cost_usd": receipt.report()["total_usd"],
                "usage": receipt.report(),
                "wall_time_seconds": wall,
                "index_dir": str(self.index_dir.resolve()),
            }

    def load_index(self) -> bool:
        """Load a previously saved index. Returns True if ready."""
        if not self.index_files_present():
            self._ready = False
            return False

        with open(self.meta_path) as f:
            meta = json.load(f)

        self.parent_size = meta.get("parent_size", self.parent_size)
        self.child_size = meta.get("child_size", self.child_size)
        self.collection = meta.get("collection", self.collection)
        self.chunker = ParentChildChunker(
            parent_size=self.parent_size, child_size=self.child_size
        )

        with open(self.parents_path, "rb") as f:
            parents = [DocumentChunk.model_validate(c.model_dump()) for c in pickle.load(f)]
        with open(self.children_path, "rb") as f:
            self.children = [DocumentChunk.model_validate(c.model_dump()) for c in pickle.load(f)]

        if not self.children:
            self._ready = False
            return False

        self.parent_store = {p.chunk_id: p for p in parents}
        self.documents = [IndexedDocument(**d) for d in meta.get("documents", [])]

        self.vector = None
        self.bm25 = None
        self.hybrid = None
        self.generator = None
        self.query_pipeline = None
        self._ensure_retrievers(reset_vector=False)
        assert self.bm25 is not None and self.hybrid is not None
        self.bm25.index(self.children)
        # Vector store already has embeddings on disk — do not re-index
        self.hybrid.parent_store = self.parent_store

        self._ready = True
        return True

    def _save_index(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        parents = list(self.parent_store.values())
        with open(self.parents_path, "wb") as f:
            pickle.dump(parents, f)
        with open(self.children_path, "wb") as f:
            pickle.dump(self.children, f)

        meta = {
            "strategy": "parent_child",
            "evidence_revision": 1,
            "parent_size": self.parent_size,
            "child_size": self.child_size,
            "collection": self.collection,
            "n_parents": len(parents),
            "n_children": len(self.children),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": settings.embedding_model,
            "generator_model": settings.llm_model,
            "documents": [asdict(d) for d in self.documents],
        }
        with open(self.meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def _reset_index_state(self) -> None:
        self.parent_store = {}
        self.children = []
        self.documents = []
        self._ready = False
        if self.vector is not None:
            try:
                self.vector.reset()
            except Exception:
                pass
        if self.chroma_dir.exists():
            shutil.rmtree(self.chroma_dir, ignore_errors=True)
        # Also clear stale pickle/meta so a failed rebuild cannot leave a half-ready index
        for path in (self.parents_path, self.children_path, self.meta_path):
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
        self.vector = None
        self.bm25 = None
        self.hybrid = None
        self.generator = None
        self.query_pipeline = None

    # ------------------------------------------------------------------
    # Online query (no Ragas)
    # ------------------------------------------------------------------
    def query(
        self,
        question: str,
        *,
        verify_hallucination: bool = False,
        require_api_key: bool = True,
    ) -> QueryResult:
        if require_api_key:
            self.require_openai_key()

        question = (question or "").strip()
        if not question:
            raise ValueError("Question must be a non-empty string.")

        if not self.is_ready():
            if not self.load_index():
                raise RuntimeError(
                    "No index loaded. Run ingest_and_index() or scripts/build_index.py first."
                )

        with self.cost_tracker.request() as receipt:
            assert self.query_pipeline is not None
            t0 = time.perf_counter()
            result = self.query_pipeline.query(question)

            doc_names = {
                d.document_id: Path(d.source_path).name for d in self.documents
            }
            chunks = result.get("chunks", [])
            def card(chunk, number):
                spans = getattr(chunk, "evidence_spans", [])
                version = getattr(chunk, "source_version", None)
                return {
                    "chunk_id": chunk.chunk_id, "source_number": number,
                    "text_preview": chunk.text[:200], "text": chunk.text,
                    "page_number": chunk.page_number,
                    "page_numbers": sorted({s.page_number for s in spans if s.page_number is not None}),
                    "heading_path": list(chunk.heading_path),
                    "document_id": chunk.document_id, "source_version": version,
                    "document_name": doc_names.get(chunk.document_id, ""),
                    "evidence_spans": [s.model_dump() for s in spans],
                    "provenance_status": "resolved" if version and spans else "migration_required",
                    "legacy_document_id": chunk.document_id if not version or not spans else None,
                }
            retrieved_contexts = [card(c, i) for i, c in enumerate(chunks, 1)]
            lookup = {c["chunk_id"]: c for c in retrieved_contexts}
            citations = [lookup[cid] for cid in result.get("citations", []) if cid in lookup]

            hallucination = None
            if verify_hallucination:
                hallucination = self.verify_hallucination(
                    result.get("answer", ""), result.get("chunks", [])
                )

            usage = receipt.report()
            return QueryResult(
                query=question,
                answer=result.get("answer", ""),
                citations=citations,
                retrieved_contexts=retrieved_contexts,
                candidates=result.get("candidates", []),
                invalid_citations=result.get("invalid_citations", []) + [cid for cid in result.get("citations", []) if cid not in lookup],
                chunks=result.get("chunks", []),
                refused=result.get("refused", False),
                query_type=result.get("query_type"),
                stages=result.get("stages", []),
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                retrieval_latency_ms=result.get("retrieval_latency_ms", 0),
                outcome=result.get("outcome"),
                usage=usage,
                configuration={"generator_model": getattr(self.generator, "model", None),
                               "embedding_model": getattr(self.vector, "embedding_model", None),
                               "judge_model": settings.judge_model if verify_hallucination else None,
                               "verify_hallucination": verify_hallucination,
                               "quick_k": getattr(self.query_pipeline, "quick_k", None),
                               "deep_k": getattr(self.query_pipeline, "deep_k", None)},
                n_chunks_retrieved=len(result.get("chunks", [])),
                cost_usd=usage["total_usd"],
                cost_breakdown=usage["by_stage"],
                hallucination=hallucination,
            )

    def verify_hallucination(
        self, answer: str, chunks: list[DocumentChunk]
    ) -> dict[str, Any]:
        """Optional claim-level check — kept off the default online path."""
        from src.evaluators import HallucinationDetector

        detector = HallucinationDetector(cost_tracker=self.cost_tracker)
        report = detector.detect(answer, chunks)
        return report.to_dict()

    # ------------------------------------------------------------------
    # Offline evaluation (Ragas)
    # ------------------------------------------------------------------
    def evaluate(
        self,
        golden_set: list[dict[str, Any]] | str | Path,
        *,
        limit: Optional[int] = None,
        verbose: bool = True,
        output_csv: Optional[str | Path] = None,
        require_api_key: bool = True,
    ) -> dict[str, Any]:
        from src.evaluators import RagasEvaluator

        if require_api_key:
            self.require_openai_key()

        if not self.is_ready():
            if not self.load_index():
                raise RuntimeError("No index loaded. Build or load an index first.")

        if isinstance(golden_set, (str, Path)):
            golden_path = Path(golden_set)
            if not golden_path.is_absolute():
                golden_path = (settings.repo_root / golden_path).resolve()
            examples = RagasEvaluator.load_golden_set(golden_path)
        else:
            examples = list(golden_set)

        if limit is not None:
            examples = examples[:limit]

        evaluator = RagasEvaluator(cost_tracker=self.cost_tracker)
        assert self.query_pipeline is not None

        def query_fn(question: str) -> dict[str, Any]:
            return asdict(self.query(question, require_api_key=require_api_key))

        with self.cost_tracker.request() as receipt:
            t0 = time.perf_counter()
            df = evaluator.evaluate(query_fn, examples, verbose=verbose)
            wall = time.perf_counter() - t0

            if output_csv is not None:
                out = Path(output_csv)
                if not out.is_absolute():
                    out = settings.repo_root / out
                out.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(out, index=False)
                out.with_suffix(out.suffix + ".usage.json").write_text(json.dumps({
                    "usage": receipt.report(),
                    "configuration": {"judge_model": evaluator.llm_model, "judge_embedding_model": evaluator.embedding_model},
                }, indent=2) + "\n")
                output_csv = out

            metric_cols = [
                c
                for c in (
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision",
                    "context_recall",
                )
                if c in df.columns
            ]
            summary = {c: float(df[c].mean()) if df[c].count() else None for c in metric_cols} if metric_cols else {}
            by_category = None
            if metric_cols and "category" in df.columns:
                by_category = (
                    df.groupby("category")[metric_cols].mean().round(3).astype(object).where(
                        df.groupby("category")[metric_cols].mean().notna(), None
                    ).to_dict()
                )

            return {
                "n_examples": len(examples),
                "metrics": summary,
                "metric_denominators": {c: int(df[c].count()) for c in metric_cols},
                "by_category": by_category,
                "by_category_denominators": df.groupby("category")[metric_cols].count().to_dict() if "category" in df.columns else {},
                "dataframe": df,
                "cost_usd": receipt.report()["total_usd"],
                "usage": receipt.report(),
                "configuration": {"judge_model": evaluator.llm_model, "judge_embedding_model": evaluator.embedding_model},
                "wall_time_seconds": wall,
                "output_csv": str(output_csv) if output_csv else None,
            }
