"""UTF-8 text, Markdown headings, and static HTML snapshots without model calls."""
from html.parser import HTMLParser
import hashlib
import re

from src.core.models import Document, DocumentBlock
from src.storage.objects import MAX_BYTES


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden += 1
        if not self.hidden and tag in ('p', 'div', 'br', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden = max(0, self.hidden-1)
        if not self.hidden and tag in ('p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text + ' ')


def load_text(data, kind, title):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Text must be between 1 byte and 20 MiB')
    text = data.decode('utf-8-sig', errors='strict')
    if '\x00' in text:
        raise ValueError('Text contains NUL bytes')
    if kind == 'html':
        parser = _HTMLText()
        parser.feed(text)
        text = '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
    blocks, heading, pending, start, fenced = [], [], [], 1, False
    def flush():
        if pending:
            blocks.append(DocumentBlock(block_type='paragraph', text='\n'.join(pending),
                                        line_start=start, heading_path=heading.copy()))
            pending.clear()
    for number, line in enumerate(text.splitlines(), 1):
        if kind == 'markdown' and line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
        match = re.match(r'^(#{1,4})\s+(.+?)\s*#*$', line) if kind == 'markdown' and not fenced else None
        if match:
            flush()
            level, name = len(match[1]), match[2]
            heading = heading[:level-1] + [name]
            blocks.append(DocumentBlock(block_type=f'h{level}', text=line, line_start=number, heading_path=heading.copy()))
        elif not line.strip():
            flush()
        else:
            if not pending:
                start = number
            pending.append(line)
    flush()
    if not blocks:
        raise ValueError('Source has no extractable text')
    return Document(title=title, source_type=kind, source_hash=hashlib.sha256(data).hexdigest(), blocks=blocks)
