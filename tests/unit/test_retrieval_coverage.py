"""Offline checks for the bounded, opt-in parent evidence supplement."""
import pytest

from src.core.models import DocumentChunk
from src.retrievers.hybrid import HybridRetriever, supplement_parent_evidence


def chunk(identity, text, parent=None):
    return DocumentChunk(chunk_id=identity, document_id="authorized", text=text, parent_chunk_id=parent)


def test_parent_supplement_preserves_default_and_bounded_original_evidence():
    parents = {f"p{i}": chunk(f"p{i}", f"Unique topic {i}") for i in range(12)}
    parents["growth"] = chunk("growth", "[Repeated heading]\nRevenue up 39%; continued ramp.")
    children = [chunk(f"c{i}", "Unique", f"p{i}") for i in range(12)]
    children += [chunk("duplicate", "Unique", "p2"), chunk("unauthorized", "Growth", "other-owner")]
    base = [parents["p0"], parents["p1"]]
    assert supplement_parent_evidence("growth", base, children, parents) is base
    result = supplement_parent_evidence("Are businesses reporting growth?", base, children, parents, 8)
    assert result[:2] == base
    assert result[2:8] == [parents[f"p{i}"] for i in range(2, 8)]
    assert parents["growth"] in result
    assert len(result) <= 10 and len({c.chunk_id for c in result}) == len(result)
    assert all(c is parents[c.chunk_id] for c in result)
    assert parents["growth"].retrieval_text is None
    assert all(c.document_id == "authorized" for c in result)


def test_parent_supplement_does_not_append_zero_score_neighbors():
    base = [chunk("base", "apples")]
    pool = {"base": base[0], "other": chunk("other", "oranges")}
    assert supplement_parent_evidence("unmatched", base, [], pool, 8) == base
    for invalid in (-1, 9, True, 1.5):
        with pytest.raises(ValueError):
            supplement_parent_evidence("anything", base, [], pool, invalid)


def test_hybrid_supplement_keeps_fused_child_candidates_unchanged():
    parents = {f"p{i}": chunk(f"p{i}", f"Financial topic {i}") for i in range(10)}
    children = [chunk(f"c{i}", "Financial", f"p{i}") for i in range(10)]

    class Branch:
        def search_with_scores(self, query, k):
            return [(c, 1.0) for c in children[:k]]

    retriever = HybridRetriever(Branch(), Branch(), parents)
    baseline = retriever.retrieve_with_candidates("Financial", k=3)
    changed = retriever.retrieve_with_candidates("Financial", k=3, supplement_k=8)
    assert changed["candidates"] == baseline["candidates"]
    assert changed["chunks"][:3] == baseline["chunks"]
    assert len(changed["chunks"]) <= 11
    assert retriever.retrieve_with_candidates("Financial", k=3, use_parent=False, supplement_k=8)["chunks"] == baseline["candidates"][:3]


def test_postgres_aliases_use_authorized_confirmed_source_or_version_snapshot():
    from contextlib import nullcontext
    from src.retrievers.postgres import PostgresRetriever

    parent = chunk("p", "Original revenue row")
    parent.metadata = {"build_id": "owned-build", "confirmed_source_metadata": {"company_name": "Stale"}}
    child = chunk("c", "Original revenue row", "p")
    profile = {"review_status": "confirmed", "company_id": "issuer", "company_name": "Owned Issuer"}

    class Rows:
        def __init__(self, rows): self.rows = rows
        def fetchall(self): return self.rows

    class Database:
        def execute(self, sql, args=None):
            if sql.startswith("SELECT b.*"):
                assert "s.owner_id=%s" in sql and "s.status<>'archived'" in sql
                self.metadata_alias = "v" if "v.metadata AS source_metadata" in sql else "s"
                return Rows([{"build_id": "owned-build", "source_metadata": profile,
                              "manifest": {"embedding_model": "offline", "dimensions": 3, "distance": "cosine"}}]
                            if args[0] == "owner" else [])
            if "SELECT payload,parent_id" in sql:
                return Rows([{"payload": c.model_dump(), "parent_id": c.parent_chunk_id} for c in (parent, child)])
            if "JOIN chunk_embeddings" in sql:
                return Rows([{"payload": child.model_dump(), "distance": 0.0}])
            return Rows([])

    class Registry:
        def connect(self): return nullcontext(db)

    class Embeddings:
        def embed_query(self, query): return [1, 0, 0]

    db = Database()
    retriever = PostgresRetriever(Registry(), "owner", Embeddings(), "offline", 3)
    result = retriever.retrieve_with_candidates("revenue", supplement_k=8)
    assert db.metadata_alias == "s"
    assert result["chunks"][0].metadata["confirmed_source_metadata"] == profile
    assert parent.metadata["confirmed_source_metadata"]["company_name"] == "Stale"
    assert "confirmed_source_metadata" not in result["candidates"][0].metadata
    version = "11111111-1111-4111-8111-111111111111"
    filtered = PostgresRetriever(Registry(), "owner", Embeddings(), "offline", 3,
                                 {"source_id": version, "version_id": version})
    filtered.retrieve_with_candidates("revenue")
    assert db.metadata_alias == "v"
    profile["review_status"] = "unreviewed"
    assert "confirmed_source_metadata" not in retriever.retrieve("revenue")[0].metadata
    assert PostgresRetriever(Registry(), "other-owner", Embeddings(), "offline", 3).retrieve("revenue") == []
