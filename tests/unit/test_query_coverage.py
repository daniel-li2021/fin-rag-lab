"""Bounded opt-in coverage reaches retrieval without changing shared state."""
import pytest
from pydantic import ValidationError

from src.api.private_server import PrivateQuery
from src.api.server import QueryRequest
from src.core.models import DocumentChunk
from src.pipelines.query import QueryPipeline


def test_query_coverage_is_request_scoped_and_bounded():
    class Retriever:
        calls = []
        def retrieve_with_candidates(self, query, k, **options):
            self.calls.append((k, options))
            return {"chunks": [DocumentChunk(chunk_id="one", document_id="doc", text="evidence")], "candidates": []}

    class Generator:
        calls = []
        def generate(self, query, chunks, **options):
            self.calls.append(options)
            return {"answer": "Supported", "outcome": "answer", "citations": []}

    retriever = Retriever()
    generator = Generator()
    pipeline = QueryPipeline(retriever, generator)
    pipeline.query("What was revenue?", supplement_k=6)
    pipeline.query("What was revenue?")
    assert retriever.calls == [(3, {"supplement_k": 6}), (3, {})]
    assert generator.calls == [{"financial_evidence": True}, {}]
    for value in (-1, 9, True, 1.5, "6"):
        with pytest.raises(ValueError):
            pipeline.query("What was revenue?", supplement_k=value)
    assert len(retriever.calls) == 2


def test_api_coverage_bounds_match_pipeline():
    for schema in (PrivateQuery, QueryRequest):
        assert schema(question="Revenue?").supplement_k == 0
        assert schema(question="Revenue?", supplement_k=8).supplement_k == 8
        for value in (-1, 9, True, "6"):
            with pytest.raises(ValidationError):
                schema(question="Revenue?", supplement_k=value)
