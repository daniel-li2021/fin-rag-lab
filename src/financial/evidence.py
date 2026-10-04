"""Task-scoped original passage search; lexical matches are candidates, never reviewed facts."""
import hashlib
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.models import DocumentChunk
from src.storage.models import ResearchSelection
from src.retrievers.bm25 import BM25Retriever, _tokenize
from src.chunkers._token_utils import get_encoding
from .research import _canonical


class EvidenceTask(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)
    task_id: str = Field(min_length=1, max_length=100)
    company_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=1000)
    repair_query: str | None = Field(default=None, min_length=1, max_length=1000)
    document_period_label: str | None = Field(default=None, min_length=1, max_length=200)


class EvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    question: str = Field(min_length=1, max_length=4000)
    selections: tuple[ResearchSelection, ...] = Field(min_length=1, max_length=18)
    tasks: tuple[EvidenceTask, ...] = Field(min_length=1, max_length=6)
    as_of: date | None = None
    synthesize: bool = False

    @model_validator(mode='after')
    def bounds(self):
        if len({t.task_id for t in self.tasks}) != len(self.tasks) or len({t.company_id for t in self.tasks}) > 3:
            raise ValueError('Evidence tasks require unique IDs and at most three companies')
        if len({t.document_period_label for t in self.tasks if t.document_period_label}) > 3:
            raise ValueError('Narrow evidence search to three document periods')
        return self


def search_evidence(request: EvidenceSearchRequest, snapshot):
    encoder = get_encoding()
    pins = snapshot['sources']
    inventory = {i['source_id']: i for i in snapshot['inventory']}
    budget = 6000 // len(request.tasks)
    coverage, passages, attempts = [], [], {}
    for task in request.tasks:
        sources = [p for p in pins if p.company_id == task.company_id]
        if request.as_of and any(p.publication_date is None for p in sources):
            coverage.append({'task_id': task.task_id, 'status': 'ambiguous',
                             'reason': 'Unknown publication date prevents historical evidence selection'})
            attempts[task.task_id] = 0
            continue
        if request.as_of:
            sources = [p for p in sources if p.publication_date <= request.as_of]
        if task.document_period_label:
            sources = [p for p in sources if (inventory[p.source_id]['metadata'].get('period_label') or '').casefold()
                       == task.document_period_label.casefold()]
        if not sources:
            present = any(i['metadata'].get('company_id') == task.company_id for i in snapshot['inventory'])
            coverage.append({'task_id': task.task_id, 'status': 'source_unavailable' if present else 'source_absent',
                             'reason': 'No confirmed available source matches the requested company/document period'})
            attempts[task.task_id] = 0
            continue
        chunks, originals = [], {}
        neighbors = {}
        for pin in sources:
            source_blocks = snapshot['blocks'].get(pin.build_id, [])
            for position, block in enumerate(source_blocks):
                text = block.get_original_text()
                if not _tokenize(text):
                    continue
                identity = hashlib.sha256(f'{pin.build_id}:{block.block_id}'.encode()).hexdigest()
                chunks.append(DocumentChunk(chunk_id=identity, document_id=pin.source_id, text=text))
                originals[identity] = (pin, block)
                neighbors[identity] = [(pin, b) for b in source_blocks[max(0,position-1):position+2]
                                       if b.block_id != block.block_id and b.page_number == block.page_number]
        retriever = BM25Retriever()
        retriever.index(chunks)
        chosen, used, exhausted = [], 0, False
        attempts[task.task_id] = 0
        for query in (task.query, task.repair_query):
            if query is None or chosen:
                break
            attempts[task.task_id] += 1
            tokens = set(_tokenize(query))
            # Match at least one requested term independently of BM25's corpus-relative score sign.
            for chunk, score in retriever.search_with_scores(query, k=min(10000, len(chunks))):
                if not tokens.intersection(_tokenize(chunk.text)):
                    continue
                count = len(encoder.encode(chunk.text))
                if used + count > budget:
                    exhausted = True
                    continue
                pin, block = originals[chunk.chunk_id]
                chosen.append({'task_id': task.task_id, 'evidence_id': chunk.chunk_id, 'source': pin.model_dump(mode='json'),
                    'block_id': block.block_id, 'page_number': block.page_number, 'char_start': 0,
                    'char_end': len(chunk.text), 'text': chunk.text, 'tokens': count, 'score': float(score)})
                used += count
                if len(chosen) == 3:
                    break
        # Original headings and bullet introductions often occupy separate PDF blocks.
        # Preserve adjacent original context with its own locator and the same task budget.
        seen = {p['evidence_id'] for p in chosen}
        for anchor in tuple(chosen):
            for pin, block in neighbors.get(anchor['evidence_id'], []):
                identity = hashlib.sha256(f'{pin.build_id}:{block.block_id}'.encode()).hexdigest()
                text = block.get_original_text()
                count = len(encoder.encode(text))
                if identity in seen or not _tokenize(text) or used+count > budget:
                    continue
                chosen.append({'task_id': task.task_id, 'evidence_id': identity, 'source': pin.model_dump(mode='json'),
                    'block_id': block.block_id, 'page_number': block.page_number, 'char_start': 0,
                    'char_end': len(text), 'text': text, 'tokens': count, 'score': anchor['score'],
                    'context_for': anchor['evidence_id']})
                seen.add(identity)
                used += count
        passages.extend(chosen)
        coverage.append({'task_id': task.task_id, 'status': 'binding_unverified' if chosen else 'passage_not_found',
            'reason': 'Original candidates require topic/period review before synthesis' if chosen else
                      'Matching original blocks exceed the allocated evidence budget' if exhausted else 'No original lexical match',
            'evidence_ids': [p['evidence_id'] for p in chosen], 'budget_exhausted': exhausted})
    result = {'contract_version': 'evidence-search-v1', 'request': request.model_dump(mode='json'),
        'outcome': 'clarify' if any(c['status'] == 'ambiguous' for c in coverage) else 'qualified_answer' if passages else 'refuse',
        'answer': 'Original passage candidates; relevance and reporting-time coverage require review.' if passages else
                  'No requested original evidence was found within the selected sources and budget.',
        'manifest': [p.model_dump(mode='json') for p in pins], 'inventory': snapshot['inventory'],
        'coverage': coverage, 'passages': passages, 'calculations': [], 'observations': [],
        'citations': {p['evidence_id']: p for p in passages}, 'attempts': attempts,
        'original_tokens': sum(p['tokens'] for p in passages), 'evidence_token_ceiling': 6000,
        'usage': {'planner_calls': 0, 'generator_calls': 0, 'embedding_calls': 0, 'cost_usd': '0'}}
    result['run_id'] = hashlib.sha256(_canonical(result).encode()).hexdigest()
    return result
