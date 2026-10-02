"""
FastAPI demo server — thin HTTP adapter over RAGService.

Endpoints:
  GET  /health
  POST /ingest   {"path": "...", "max_pages": int?}
  POST /query    {"question": "...", "verify_hallucination": bool?}

Uses the same parent-child hybrid path as the CLI and Streamlit app.
Run from repo root:
    uvicorn src.api.server:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.core.config import settings, configure_langsmith
from src.services import RAGService


class IngestRequest(BaseModel):
    path: str = Field(..., description="Absolute or repo-relative path to a PDF")
    max_pages: Optional[int] = None
    page_range: Optional[tuple[int, int]] = None


class IngestResponse(BaseModel):
    document_id: str
    title: str
    n_blocks: int
    n_chunks: int
    cost_usd: Optional[float]
    cache_hit: bool
    n_documents_indexed: int
    usage: dict[str, Any] = {}


class QueryRequest(BaseModel):
    question: str
    verify_hallucination: bool = False


class CitationModel(BaseModel):
    chunk_id: str
    text_preview: str
    page_number: Optional[int] = None
    heading_path: list[str] = []
    source_number: Optional[int] = None
    document_id: str = ""
    document_name: str = ""
    source_version: Optional[str] = None
    page_numbers: list[int] = []
    evidence_spans: list[dict[str, Any]] = []
    provenance_status: str = "migration_required"
    legacy_document_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationModel]
    retrieved_contexts: list[CitationModel] = []
    invalid_citations: list[Any] = []
    refused: bool
    query_type: Optional[str] = None
    stages: list[str] = []
    n_chunks_retrieved: int
    latency_ms: float = 0.0
    cost_usd: Optional[float] = 0.0
    hallucination: Optional[dict[str, Any]] = None
    outcome: Optional[str] = None
    usage: dict[str, Any] = {}
    configuration: dict[str, Any] = {}
    cost_breakdown: dict[str, Optional[float]] = {}
    retrieval_latency_ms: float = 0.0


class AppState:
    """Holds the shared RAGService instance for the HTTP process."""

    def __init__(self, service: Optional[RAGService] = None):
        self.service = service or RAGService(
            index_dir=settings.repo_root / "index",
            cache_root=settings.repo_root / "cache",
            upload_dir=settings.repo_root / "data" / "uploads",
        )
        # Best-effort load so /query works after restart if index/ exists
        self.service.load_index()


def build_app(service: Optional[RAGService] = None) -> FastAPI:
    """Factory — pass a prebuilt RAGService for tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_langsmith()
        yield

    app = FastAPI(
        title="Fin-RAG Lab API",
        version="1.1.0",
        description="Parent-child hybrid RAG. POST /ingest, then POST /query.",
        lifespan=lifespan,
    )
    state = AppState(service=service)

    @app.get("/health")
    def health():
        status = state.service.status()
        return {
            "status": "ok",
            "ready": status.ready,
            "n_documents_indexed": status.n_documents,
            "n_children": status.n_children,
            "n_parents": status.n_parents,
            "openai_key_set": status.openai_key_set,
            "strategy": status.strategy,
            "index_dir": status.index_dir,
        }

    @app.post("/ingest", response_model=IngestResponse)
    def ingest(req: IngestRequest):
        path = Path(req.path)
        if not path.is_absolute():
            path = (settings.repo_root / path).resolve()
        if not path.exists():
            raise HTTPException(404, f"file not found: {path}")

        try:
            result = state.service.ingest_and_index(
                [path],
                max_pages=req.max_pages,
                page_range=req.page_range,
                reset=True,
            )
        except RuntimeError as e:
            # Missing API key, empty chunks, etc.
            raise HTTPException(400, str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e
        except Exception as e:
            raise HTTPException(500, f"ingest failed: {e}") from e

        doc = result["documents"][0]
        return IngestResponse(
            document_id=doc["document_id"],
            title=doc["title"],
            n_blocks=doc["n_blocks"],
            n_chunks=doc["n_children"],
            cost_usd=result["cost_usd"],
            usage=result["usage"],
            cache_hit=doc["cache_hit"],
            n_documents_indexed=result["n_documents"],
        )

    @app.post("/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        if not state.service.is_ready():
            if not state.service.load_index():
                raise HTTPException(
                    400, "No documents indexed. POST /ingest first (or build_index.py)."
                )
        try:
            result = state.service.query(
                req.question,
                verify_hallucination=req.verify_hallucination,
            )
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(500, f"query failed: {e}") from e

        citations = [CitationModel(**c) for c in result.citations]
        return QueryResponse(
            answer=result.answer,
            citations=citations,
            retrieved_contexts=[CitationModel(**c) for c in result.retrieved_contexts],
            invalid_citations=result.invalid_citations,
            refused=result.refused,
            query_type=result.query_type,
            stages=result.stages,
            n_chunks_retrieved=result.n_chunks_retrieved,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            hallucination=result.hallucination,
            outcome=result.outcome, usage=result.usage,
            configuration=result.configuration, cost_breakdown=result.cost_breakdown,
            retrieval_latency_ms=result.retrieval_latency_ms,
        )

    return app


import os
if os.getenv('DATABASE_URL'):
    from .private_server import build_private_app
    app = build_private_app()
else:
    app = build_app()
