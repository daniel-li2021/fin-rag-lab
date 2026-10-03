"""
HybridRetriever: composes Vector + BM25 + RRF + (optional) parent-child swap.

This is what production RAG looks like in 2026:
  1. Run vector and BM25 in parallel (both retrieve top-fetch_k)
  2. Merge with RRF (k=60) into a single ranked list
  3. If parent-child enabled, swap each child for its parent (deduped)
  4. Return top-k
"""
from __future__ import annotations
import re
from typing import Optional

from langsmith import traceable

from src.core.interfaces import BaseRetriever
from src.core.models import DocumentChunk
from .rrf import rrf_merge
from .bm25 import BM25Retriever


def supplement_parent_evidence(query, chunks, candidates, parent_store, supplement_k=0):
    """Opt-in bounded coverage; original rankings and evidence are never rewritten."""
    if type(supplement_k) is not int or not 0 <= supplement_k <= 8:
        raise ValueError("supplement_k must be between 0 and 8")
    if not supplement_k or not parent_store:
        return chunks
    result, seen = list(chunks), {c.chunk_id for c in chunks}
    limit = len(result) + supplement_k
    # Reserve two slots for evidence outside the fused child shortlist.
    for child in candidates:
        parent = parent_store.get(child.parent_chunk_id)
        if parent and parent.chunk_id not in seen and len(result) < limit - min(2, supplement_k):
            result.append(parent); seen.add(parent.chunk_id)
    lexical = BM25Retriever()
    lexical.index([c.model_copy(update={"retrieval_text": re.sub(r"^\[[^\n]+\]\s*", "", c.text, flags=re.M)})
                   for c in parent_store.values()])
    # ponytail: lexical synonyms cover explicit growth requests; not a metric planner.
    probes = [query]
    if re.search(r"\b(growth|grew|growing)\b", query, re.I):
        probes.insert(0, "growth up ramp")
    for probe in probes:
        for parent, score in lexical.search_with_scores(probe, k=20):
            if len(result) >= limit:
                return result
            if score > 0 and parent.chunk_id not in seen:
                result.append(parent_store[parent.chunk_id]); seen.add(parent.chunk_id)
    return result


class HybridRetriever(BaseRetriever):
    name = "hybrid"
    
    def __init__(
        self,
        vector,                         # VectorRetriever
        bm25,                           # BM25Retriever
        parent_store: Optional[dict[str, DocumentChunk]] = None,
        rrf_k: int = 60,
    ):
        self.vector = vector
        self.bm25 = bm25
        self.parent_store = parent_store or {}
        self.rrf_k = rrf_k
    
    def index(self, chunks: list[DocumentChunk]) -> None:
        """Index into both vector + BM25."""
        self.vector.index(chunks)
        self.bm25.index(chunks)
    
    @traceable(name="hybrid_retrieve")
    def retrieve(
        self,
        query: str,
        k: int = 5,
        fetch_k: int = 20,
        use_parent: bool = True,
    ) -> list[DocumentChunk]:
        return self.retrieve_with_candidates(query, k, fetch_k, use_parent)["chunks"]

    def retrieve_with_candidates(self, query, k=5, fetch_k=20, use_parent=True, supplement_k=0):
        """Return the exact fused child candidates used by this request, without replay."""
        vec_scored = self.vector.search_with_scores(query, k=fetch_k)
        bm25_scored = self.bm25.search_with_scores(query, k=fetch_k)
        fused = rrf_merge([vec_scored, bm25_scored], k=self.rrf_k, top_n=fetch_k)
        candidates = [c.model_copy(update={"metadata": {**c.metadata, "rrf_score": score}}) for c, score in fused]
        chunks = self._swap_to_parents(fused, k) if use_parent and self.parent_store else candidates[:k]
        if use_parent:
            chunks = supplement_parent_evidence(query, chunks, candidates, self.parent_store, supplement_k)
        return {"chunks": chunks, "candidates": candidates}

    def _swap_to_parents(
        self, fused: list[tuple[DocumentChunk, float]], k: int
    ) -> list[DocumentChunk]:
        seen: set[str] = set()
        out: list[DocumentChunk] = []
        for child, _ in fused:
            pid = child.parent_chunk_id
            if pid:
                if pid in seen or pid not in self.parent_store:
                    continue
                seen.add(pid)
                out.append(self.parent_store[pid])
            else:
                out.append(child)
            if len(out) >= k:
                break
        return out
