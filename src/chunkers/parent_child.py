"""
S4 §4.5 Strategy D: Parent-Child (small-to-big retrieval).

Core insight:
  "The best chunk size for retrieval is not the best chunk size for generation."

Children are tiny (~150 tokens) → precise embedding match.
Parents are big (~800 tokens) → enough context for the LLM to reason.
Each child has parent_chunk_id pointing back to its parent.
"""
from __future__ import annotations
from ._evidence import evidence_text, make_chunk, split_spans

from src.core.interfaces import BaseChunker
from src.core.models import Document, DocumentChunk
from ._token_utils import get_token_counter


class ParentChildChunker(BaseChunker):
    name = "parent_child"
    
    def __init__(
        self,
        parent_size: int = 800,
        child_size: int = 150,
        parent_overlap: int = 80,
        child_overlap: int = 20,
        model: str = "gpt-4o",
    ):
        self.parent_size = parent_size
        self.child_size = child_size
        self.parent_overlap = parent_overlap
        self.child_overlap = child_overlap
        self.model = model
    
    def chunk(self, doc: Document) -> list[DocumentChunk]:
        """Returns children only (what goes in vector DB)."""
        _, children = self.chunk_with_parents(doc)
        return children
    
    def chunk_with_parents(
        self, doc: Document
    ) -> tuple[list[DocumentChunk], list[DocumentChunk]]:
        token_count = get_token_counter(self.model)
        text, ranges = evidence_text(doc)
        parents, children = [], []
        for start, end in split_spans(text, self.parent_size, self.parent_overlap, token_count):
            parent = make_chunk(doc, text, ranges, start, end,
                                metadata={"chunker": self.name, "level": "parent", "evidence_revision": 1})
            if parent is None:
                continue
            parents.append(parent)
            for lo, hi in split_spans(text[start:end], self.child_size, self.child_overlap, token_count, offset=start):
                child = make_chunk(doc, text, ranges, lo, hi,
                                          parent_chunk_id=parent.chunk_id,
                                          metadata={"chunker": self.name, "level": "child", "evidence_revision": 1})
                if child is not None:
                    children.append(child)
        return parents, children
