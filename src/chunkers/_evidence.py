"""Offset-preserving splitting and block provenance shared by experiment arms."""
import hashlib
import re

from src.core.models import DocumentChunk, EvidenceSpan

SEPARATORS = ('\n\n', '\n', '. ', '? ', '! ', ' ', '')


def _split_spans(text, size, overlap, length, separators=SEPARATORS, offset=0):
    """Recursive splitting with carried offsets, never searching repeated output text.

    Mirrors separator/overlap merging, but measures tokens and retains original
    character boundaries. A single indivisible character can exceed the budget.
    """
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError('Require size > 0 and 0 <= overlap < size')
    separator = next((s for s in separators if not s or s in text), '')
    remaining = separators[separators.index(separator) + 1:]
    starts = [0] + [m.start() for m in re.finditer(re.escape(separator), text) if m.start()] if separator else list(range(len(text)))
    parts = [(a, b) for a, b in zip(starts, starts[1:] + [len(text)]) if b > a]
    pending = []
    total = 0
    def emit():
        a, b = pending[0][0], pending[-1][1]
        a += len(text[a:b]) - len(text[a:b].lstrip())
        b -= len(text[a:b]) - len(text[a:b].rstrip())
        return (offset + a, offset + b)
    for a, b in parts:
        n = length(text[a:b])
        if n > size and remaining:
            if pending:
                yield emit()
                pending, total = [], 0
            yield from _split_spans(text[a:b], size, overlap, length, remaining, offset + a)
            continue
        if pending and total + n > size:
            yield emit()
            while pending and (total > overlap or total + n > size):
                first = pending.pop(0)
                total -= length(text[first[0]:first[1]])
        pending.append((a, b))
        total += n
    if pending:
        yield emit()


def split_spans(*args, **kwargs):
    for start, end in _split_spans(*args, **kwargs):
        if end > start:
            yield start, end


def evidence_text(doc, blocks=None, headings=True):
    parts, ranges = [], []
    cursor = 0
    for block in doc.blocks if blocks is None else blocks:
        if block.block_type in ('header', 'footer'):
            continue
        original = block.get_original_text()
        body = original or block.semantic_content or ''
        if not body.strip():
            continue
        prefix = '[' + ' > '.join(block.heading_path) + ']\n' if headings and block.heading_path else ''
        if not original:
            prefix += '[Generated image description; inspect the original asset]\n'
        parts.append(prefix + body + '\n\n')
        ranges.append((cursor + len(prefix), cursor + len(prefix) + len(body), block, body, bool(original)))
        cursor += len(parts[-1])
    return ''.join(parts), ranges


def make_chunk(doc, text, ranges, start, end, **kwargs):
    spans, captions = [], []
    version = doc.source_hash or 'text-sha256:' + hashlib.sha256(doc.text.encode()).hexdigest()
    for a, b, block, body, original in ranges:
        lo, hi = max(a, start), min(b, end)
        if hi <= lo:
            continue
        block_start, block_end = lo - a, hi - a
        spans.append(EvidenceSpan(
            block_id=block.block_id, source_version=version,
            page_number=block.page_number, char_start=block_start, char_end=block_end,
            line_start=(getattr(block, "line_start", None) + body[:block_start].count('\n')) if getattr(block, "line_start", None) else None,
            line_end=(getattr(block, "line_start", None) + body[:max(block_start, block_end-1)].count('\n')) if getattr(block, "line_start", None) else None,
            heading_path=block.heading_path, bbox=block.bbox,
            text=body[block_start:block_end], kind='original' if original else 'generated',
        ))
        if block.semantic_content:
            captions.append(block.semantic_content)
    if not spans:
        return None  # Heading prefixes alone are not evidence.
    chunk_text = text[start:end]
    return DocumentChunk(
        document_id=doc.document_id, source_version=version, text=chunk_text,
        retrieval_text=chunk_text + ('\n\n[Generated retrieval descriptions]\n' + '\n'.join(dict.fromkeys(captions)) if captions else ''),
        source_block_ids=list(dict.fromkeys(s.block_id for s in spans)), evidence_spans=spans,
        heading_path=list(dict.fromkeys(h for s in spans for h in s.heading_path)),
        page_number=next((s.page_number for s in spans if s.page_number is not None), None),
        **kwargs,
    )
