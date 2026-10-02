"""S4 §4.2 Strategy A: Fixed-size chunking with overlap. Class-based."""
from __future__ import annotations
from src.core.interfaces import BaseChunker
from src.core.models import Document, DocumentChunk
from ._token_utils import get_token_counter
from ._evidence import evidence_text, make_chunk, split_spans


class FixedSizeChunker(BaseChunker):
    """Naive token-based chunking. Ignores document structure entirely."""
    
    name = "fixed_size"
    
    def __init__(self, size: int = 500, overlap: int = 80, model: str = "gpt-4o"):
        self.size = size
        self.overlap = overlap
        self.model = model
    
    def chunk(self, doc: Document) -> list[DocumentChunk]:
        text, ranges = evidence_text(doc, headings=False)
        chunks = []
        for start, end in split_spans(text, self.size, self.overlap, get_token_counter(self.model), separators=("",)):
            chunk = make_chunk(doc, text, ranges, start, end,
                               metadata={"chunker": self.name, "size": self.size, "overlap": self.overlap, "evidence_revision": 1})
            if chunk is not None:
                chunks.append(chunk)
        return chunks
