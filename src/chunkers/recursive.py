"""S4 §4.3 Strategy B: Recursive splitting that respects block boundaries.

Three production tricks vs vanilla LangChain usage:
  1. Each block is split independently → chunks never cross block boundaries
  2. Token-based length function (tiktoken)
  3. heading_path is prepended to every chunk's text → cheap context enrichment
"""
from __future__ import annotations
from ._evidence import evidence_text, make_chunk, split_spans

from src.core.interfaces import BaseChunker
from src.core.models import Document, DocumentChunk
from ._token_utils import get_token_counter


class RecursiveChunker(BaseChunker):
    name = "recursive"
    
    # Block types we DON'T directly emit (they become context for paragraphs)
    _SKIP_AS_CHUNK = {"h1", "h2", "h3", "h4", "title", "header", "footer"}
    
    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 60,
        model: str = "gpt-4o",
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.model = model
    
    def chunk(self, doc: Document) -> list[DocumentChunk]:
        token_count = get_token_counter(self.model)
        chunks = []
        for block in doc.blocks:
            if block.block_type in self._SKIP_AS_CHUNK:
                continue
            text, ranges = evidence_text(doc, [block], headings=False)
            for start, end in split_spans(text, self.chunk_size, self.overlap, token_count):
                chunk = make_chunk(doc, text, ranges, start, end,
                                   metadata={"chunker": self.name, "evidence_revision": 1})
                if chunk is None:
                    continue
                if block.heading_path:
                    prefix = "[Section: " + " > ".join(block.heading_path) + "]\n"
                    chunk.text = prefix + chunk.text
                    chunk.retrieval_text = prefix + chunk.retrieval_text
                chunks.append(chunk)
        return chunks
