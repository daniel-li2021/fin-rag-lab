"""
Unit tests for RAGGenerator and QueryPipeline.

These tests don't hit the OpenAI API — we substitute a FakeLLM that returns
deterministic outputs. This is the standard pattern for testing LangChain
components offline.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from typing import Any
from src.core.models import DocumentChunk, EvidenceSpan
from src.core.interfaces import BaseRetriever, BaseGenerator
from src.generators.rag_generator import (
    RAGGenerator, _build_context, _extract_citations, _NO_RESULT_ANSWER, clarify_financial_query,
)
from src.pipelines.query import QueryPipeline, _classify_query


# =============================================================
# Helpers — build chunks + a fake LLM
# =============================================================
def make_chunks(n=3):
    return [
        DocumentChunk(
            chunk_id=f"chk_{i:03d}",
            document_id="doc_test",
            text=f"This is chunk {i} content. Net income was ${5+i}.0 billion.",
            heading_path=["Test Doc", "Section"],
            page_number=i + 1,
        )
        for i in range(n)
    ]


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content
        self.response_metadata = {}


class FakeLLM:
    """Returns a fixed answer that includes [^1] [^2] citations."""
    def __init__(self, response: str = "Answer with citation [^1] and another [^2]."):
        self.response = response
        self.last_messages = None
    def invoke(self, messages):
        self.last_messages = messages
        content = self.response if self.response.startswith("{") else json.dumps({"outcome": "answer", "answer": self.response})
        return _FakeMessage(content)


# =============================================================
# RAGGenerator tests
# =============================================================
def test_build_context_numbers_chunks():
    chunks = make_chunks(3)
    ctx, mapping = _build_context(chunks)
    assert "[Source 1]" in ctx and "[Source 2]" in ctx and "[Source 3]" in ctx
    assert mapping[1] == "chk_000"
    assert mapping[2] == "chk_001"


def test_context_uses_original_fragments_without_inherited_headings_or_captions():
    def span(text, page=1, kind='original'):
        return EvidenceSpan(block_id=text, source_version='v1', page_number=page,
                            char_start=0, char_end=len(text), text=text, kind=kind)
    chunk = DocumentChunk(document_id='acme', chunk_id='evidence', source_version='v1',
        heading_path=['Unrelated inherited heading'], text='Repeated headings interrupt the revenue sentence.',
        evidence_spans=[span('Revenue grew on strong product'), span('ramp and demand.'),
                        span('ramp and demand.'), span('Unverified generated caption', kind='generated'),
                        span('| Metric | Q4 2025 |\n| Gross margin | 54% |', page=2)])
    context, mapping = _build_context([chunk])
    assert 'Revenue grew on strong product\nramp and demand.' in context
    assert context.count('ramp and demand.') == 1
    assert 'Unrelated inherited heading' not in context and 'Unverified generated caption' not in context
    assert '[Original page 1]' in context and '[Original page 2]' in context
    assert 'version=v1' in context and '54%' in context and mapping == {1: 'evidence'}
    chunk.evidence_spans = [span('Generated caption', kind='generated')]
    assert 'Generated retrieval aid; no verified original evidence' in _build_context([chunk])[0]
    assert 'Legacy/unverified retrieval text' in _build_context(make_chunks(1))[0]


def test_confirmed_financial_ambiguity_clarifies_without_model_calls():
    chunk = make_chunks(1)[0]
    chunk.metadata['confirmed_source_metadata'] = {'company_name': 'Acme Corporation',
                                                  'company_id': 'acme', 'review_status': 'confirmed'}
    gen = RAGGenerator()
    gen._llm = FakeLLM()
    for question, dimensions in [
        ("How did Acme's automotive margins evolve in Q1 2026?", ['consolidated', 'GAAP', 'periods']),
        ('Which company has larger revenue: Acme or Other?', ['reporting period', 'revenue definition']),
        ('Which company has higher gross margin: Acme or Other?', ['reporting period', 'GAAP', 'segment scope']),
    ]:
        result = gen.generate(question, [chunk])
        assert result['outcome'] == 'clarify' and result['refused'] is False
        assert result['citations'] == [] and result['n_sources_used'] == 0
        assert all(d in result['answer'] for d in dimensions)
    assert gen._llm.last_messages is None
    assert clarify_financial_query('What was UnsupportedCo revenue?', [chunk]) is None
    assert clarify_financial_query('What was Acme gaming revenue in Q4 2025?', [chunk]) is None
    assert clarify_financial_query('Compare Acme consolidated GAAP gross margin for Q4 2025', [chunk]) is None
    chunk.metadata['confirmed_source_metadata']['review_status'] = 'unreviewed'
    assert clarify_financial_query('Compare Acme gross margin', [chunk]) is None


def test_extract_citations_finds_numbered_refs():
    answer = "The net income grew [^1]. Diluted EPS rose [^3]."
    mapping = {1: "chk_a", 2: "chk_b", 3: "chk_c"}
    cites = _extract_citations(answer, mapping)
    assert cites == ["chk_a", "chk_c"]


def test_extract_citations_dedupes():
    answer = "Claim one [^1]. Claim two also from [^1]. Claim three [^2]."
    mapping = {1: "chk_a", 2: "chk_b"}
    cites = _extract_citations(answer, mapping)
    assert cites == ["chk_a", "chk_b"]


def test_generator_refuses_on_empty():
    gen = RAGGenerator()
    gen._llm = FakeLLM()
    result = gen.generate("anything", [])
    assert result["refused"] is True
    assert result["outcome"] == "refuse"
    assert result["answer"] == _NO_RESULT_ANSWER
    assert result["citations"] == []
    assert gen._llm.last_messages is None


def test_generator_calls_llm_and_parses_citations():
    gen = RAGGenerator()
    gen._llm = FakeLLM("The net income was $5B [^1] and EPS $1.62 [^2].")
    chunks = make_chunks(3)
    result = gen.generate("What was net income?", chunks)
    
    assert result["refused"] is False
    assert "$5B" in result["answer"]
    assert len(result["citations"]) == 2
    assert result["citations"][0] == "chk_000"
    assert result["citations"][1] == "chk_001"


# =============================================================
# QueryPipeline tests
# =============================================================
def test_classify_query_factual():
    assert _classify_query("What is the net income?") == "factual_lookup"
    assert _classify_query("How much revenue did they have?") == "factual_lookup"
    assert _classify_query("How many shares were repurchased?") == "factual_lookup"


def test_classify_query_analytical():
    assert _classify_query("Compare the segments and analyze trends") == "analytical"
    long_q = "What were the main drivers of net interest income changes and how should I think about that?"
    assert _classify_query(long_q) == "analytical"


def test_classify_financial_outlook_and_results_use_deep_retrieval():
    assert _classify_query("What is Acme's AI outlook?") == "analytical"
    assert _classify_query("What were Acme's quarterly highlights?") == "analytical"
    assert _classify_query("What was Acme's Q1 revenue amount?") == "factual_lookup"


class FakeRetriever(BaseRetriever):
    name = "fake"
    def __init__(self, chunks_to_return: list[DocumentChunk]):
        self.chunks_to_return = chunks_to_return
        self.last_k = None
    def index(self, chunks):
        pass
    def retrieve(self, query: str, k: int = 5):
        self.last_k = k
        return self.chunks_to_return[:k]


class FakeGenerator(BaseGenerator):
    name = "fake_gen"
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.last_query = None
        self.last_chunks = None
    def generate(self, query, chunks):
        self.last_query = query
        self.last_chunks = chunks
        return self.response


def test_query_pipeline_factual_uses_quick_k():
    chunks = make_chunks(5)
    retriever = FakeRetriever(chunks)
    generator = FakeGenerator({
        "answer": "factual answer", "citations": ["chk_000"], "refused": False,
        "n_sources_used": 1, "n_sources_retrieved": 3,
    })
    pipeline = QueryPipeline(retriever, generator, quick_k=3, deep_k=8)
    
    result = pipeline.query("What is the net income?")
    
    assert retriever.last_k == 3, "factual queries should use quick_k"
    assert "classify→factual_lookup" in result["stages"]
    assert "quick_retrieve→3" in result["stages"]
    assert result["answer"] == "factual answer"


def test_query_pipeline_analytical_uses_deep_k():
    chunks = make_chunks(10)
    retriever = FakeRetriever(chunks)
    generator = FakeGenerator({
        "answer": "analysis", "citations": ["chk_000", "chk_002"], "refused": False,
        "n_sources_used": 2, "n_sources_retrieved": 8,
    })
    pipeline = QueryPipeline(retriever, generator, quick_k=3, deep_k=8)
    
    result = pipeline.query("Compare and contrast the segment trends across both quarters in detail")
    
    assert retriever.last_k == 8, "analytical queries should use deep_k"
    assert "deep_retrieve→8" in result["stages"]


def test_query_pipeline_refuses_on_no_chunks():
    retriever = FakeRetriever([])
    generator = FakeGenerator({"answer": "shouldn't be called", "citations": []})
    pipeline = QueryPipeline(retriever, generator)
    
    result = pipeline.query("What was Apple's revenue?")
    
    assert result["refused"] is True
    assert "refuse" in result["stages"]
    assert generator.last_query is None, "generator shouldn't run when no chunks"


def test_query_pipeline_draws_mermaid():
    pipeline = QueryPipeline(FakeRetriever([]), FakeGenerator({"answer": ""}))
    diagram = pipeline.draw_mermaid()
    assert isinstance(diagram, str)
    assert len(diagram) > 0


def test_query_pipeline_preserves_clarification_and_qualified_evidence():
    chunks = make_chunks(2)
    gen = RAGGenerator()
    question = 'Which company has higher gross margin in its most recent quarter?'
    clarification = 'Which reporting period, accounting basis and consolidated or segment scope should I compare?'
    gen._llm = FakeLLM(json.dumps({'outcome': 'clarify', 'answer': clarification}))
    pipeline = QueryPipeline(FakeRetriever(chunks), gen)
    result = pipeline.query(question)
    assert result['outcome'] == 'clarify' and result['refused'] is False
    assert result['answer'] == clarification and result['citations'] == []
    assert result['invalid_citations'] == [] and 'generate' in result['stages']
    # Subsequent supported output retains the issued source references and limitation.
    answer = 'Net income was $5.0 billion [^1]; the requested segment detail is unavailable.'
    gen._llm = FakeLLM(json.dumps({'outcome': 'qualified_answer', 'answer': answer}))
    result = pipeline.query('Summarize net income and segment detail')
    assert result['outcome'] == 'qualified_answer' and result['refused'] is False
    assert result['answer'] == answer and result['citations'] == ['chk_000']
    assert result['invalid_citations'] == []


def test_invalid_citation_numbers_are_preserved_for_audit():
    gen = RAGGenerator()
    gen._llm = FakeLLM('Claim [^1] and unresolved claim [^99].')
    result = gen.generate('What was net income?', make_chunks(1))
    assert result['citations'] == ['chk_000']
    assert result['invalid_citations'] == [99]


def test_structured_unsupported_outcome_and_malformed_output():
    import pytest
    gen = RAGGenerator()
    gen._llm = FakeLLM(json.dumps({'outcome': 'refuse', 'answer': 'Other company revenue was $99 billion. [^1]'}))
    result = gen.generate('Apple revenue?', make_chunks())
    assert result['outcome'] == 'refuse'
    assert result['refused'] is True
    assert '99' not in result['answer'] and result['citations']==[]
    gen._llm = FakeLLM(json.dumps({'outcome': 'clarify', 'answer': 'Which reporting period do you mean?'}))
    assert gen.generate('Compare revenue', make_chunks())['outcome'] == 'clarify'
    gen._llm = FakeLLM('{"answer":"Unlabeled answer"}')
    with pytest.raises(ValueError):
        gen.generate('Question', make_chunks())


def test_calculations_require_original_comparable_operands_and_render_decimal_results():
    from copy import deepcopy
    operands = [dict(source=i, company='Acme', metric='gross margin', period=period,
                     period_kind='quarterly', scope='consolidated', basis='GAAP', unit='%', value_text=value,
                     quote=f'Acme {period} consolidated GAAP gross margin {value}%')
                for i, (period, value) in enumerate([('Q4 2024', '51'), ('Q4 2025', '54')], 1)]
    chunks = [DocumentChunk(chunk_id=f'margin_{i}', document_id='acme', source_version='v1',
               text=o['quote'], evidence_spans=[EvidenceSpan(block_id=str(i), source_version='v1',
               char_start=0, char_end=len(o['quote']), text=o['quote'])])
              for i, o in enumerate(operands)]
    payload = {'outcome': 'answer', 'answer': 'Gross margin change: {calc:0}.',
               'calculations': [{'operation': 'percentage_point_change',
                                 'start': operands[0], 'end': operands[1]}]}
    gen = RAGGenerator()
    def generate(envelope):
        gen._llm = FakeLLM(json.dumps(envelope))
        return gen.generate('How did gross margin change?', chunks, financial_evidence=True)
    result = generate(payload)
    assert '+3 percentage points [^1] [^2]' in result['answer']
    assert result['outcome'] == 'answer' and result['citations'] == ['margin_0', 'margin_1']
    assert result['calculation_error'] is None
    growth = deepcopy(payload)
    growth['calculations'][0]['operation'] = 'growth'
    assert '+5.88% [^1] [^2]' in generate(growth)['answer']
    for field, value in [('unit', 'USD'), ('basis', 'non-GAAP'), ('quote', 'Gross margin 99%'),
                         ('value_text', 'NaN'), ('value_text', '4'), ('period', 'Q4 2024')]:
        invalid = deepcopy(payload)
        invalid['calculations'][0]['end'][field] = value
        result = generate(invalid)
        assert result['outcome'] == 'refuse' and result['refused'] is True
        assert result['citations'] == [] and 'Gross margin' not in result['answer']
        assert result['calculation_error']
    missing = deepcopy(payload)
    missing['answer'] = 'The increase is 3 percentage points.'
    assert generate(missing)['outcome'] == 'refuse'
    for suffix in ['YTD', 'year-to-date', 'six months', 'nine months', '12 months']:
        cumulative = deepcopy(payload)
        operand = cumulative['calculations'][0]['end']
        operand['period'] += ' ' + suffix
        operand['quote'] = operand['quote'].replace('Q4 2025', operand['period'])
        chunks[1].evidence_spans[0].text = operand['quote']
        result = generate(cumulative)
        assert result['outcome'] == 'refuse' and result['calculation_error'] == 'Period kind lacks explicit support'
    annual = deepcopy(payload)
    for i, operand in enumerate([annual['calculations'][0]['start'], annual['calculations'][0]['end']]):
        period = f'12 months ended {2024+i}'
        operand['quote'] = operand['quote'].replace(operand['period'], period)
        operand.update(period=period, period_kind='annual')
        chunks[i].evidence_spans[0].text = operand['quote']
    assert '+3 percentage points' in generate(annual)['answer']
    for chunk, operand in zip(chunks, operands):
        chunk.evidence_spans[0].text = operand['quote']
    zero = deepcopy(growth)
    zero['calculations'][0]['start'].update(value_text='0', quote='Acme Q4 2024 consolidated GAAP gross margin 0%')
    chunks[0].evidence_spans[0].text = zero['calculations'][0]['start']['quote']
    assert generate(zero)['outcome'] == 'refuse'
    missing['answer'] = 'Gross margin change: {calc:invalid}.'
    assert generate(missing)['outcome'] == 'refuse'


def test_same_period_operating_difference_and_period_kind_guard():
    from copy import deepcopy
    operands = [dict(source=i, company='Acme', metric=metric, period='Q1 2026',
                     period_kind='quarterly', scope='vehicles', basis='operating counts',
                     unit='vehicles', value_text=value,
                     quote=f'Acme Q1 2026 operating counts {metric}: {value} vehicles')
                for i, (metric, value) in enumerate([('deliveries', '358,023'), ('production', '408,386')], 1)]
    chunks = [DocumentChunk(chunk_id=f'op_{i}', document_id='acme', source_version='v1', text=o['quote'],
               evidence_spans=[EvidenceSpan(block_id=str(i), source_version='v1', char_start=0,
               char_end=len(o['quote']), text=o['quote'])]) for i, o in enumerate(operands)]
    payload = {'outcome': 'answer', 'answer': 'Production less deliveries: {calc:0}.',
               'calculations': [{'operation': 'difference', 'start': operands[0], 'end': operands[1]}]}
    gen = RAGGenerator()
    def generate(envelope):
        gen._llm = FakeLLM(json.dumps(envelope))
        return gen.generate('What is the production-delivery gap?', chunks, financial_evidence=True)
    assert '+50363 vehicles' in generate(payload)['answer']
    for field, value in [('period_kind', 'annual'), ('period', 'Q1 2025'), ('metric', 'deliveries')]:
        invalid = deepcopy(payload)
        invalid['calculations'][0]['end'][field] = value
        assert generate(invalid)['outcome'] == 'refuse'


def test_verified_citations_bind_original_quotes_and_fail_closed():
    from copy import deepcopy
    texts = ['Acme revenue was 12 million.', 'OtherCo revenue was 30 million.']
    chunks = [DocumentChunk(chunk_id=f'quote_{i}', document_id=f'doc_{i}', source_version='v1',
              text=text, evidence_spans=[EvidenceSpan(block_id=str(i), source_version='v1',
              char_start=0, char_end=len(text), text=text)]) for i, text in enumerate(texts)]
    payload = {'outcome': 'answer', 'answer': 'OtherCo revenue was 30 million [^1].',
               'citation_quotes': [{'source': 1, 'quote': texts[1]}]}
    gen = RAGGenerator()
    def generate(envelope):
        gen._llm = FakeLLM(json.dumps(envelope))
        return gen.generate('What was OtherCo revenue?', chunks, financial_evidence=True)
    result = generate(payload)
    assert result['answer'].endswith('[^2].') and result['citations'] == ['quote_1']
    assert result['citation_error'] is None
    gen._llm = FakeLLM(json.dumps({'outcome': 'answer', 'answer': 'Baseline response [^1].'}))
    assert gen.generate('Revenue?', chunks)['outcome'] == 'answer'
    assert 'citation_quotes' not in gen._llm.last_messages[0].content
    assert '[Original page' not in gen._llm.last_messages[1].content
    malformed = deepcopy(payload)
    malformed['citation_quotes'][0]['source'] = '[Source 1]'
    assert generate(malformed)['citation_error'] == 'Malformed citation/calculation evidence'
    clarification = deepcopy(payload)
    clarification.update(outcome='clarify', citation_quotes=[])
    assert generate(clarification)['outcome'] == 'refuse'
    for records in [[], [{'source': 1, 'quote': '30'}],
                    [{'source': 1, 'quote': 'Invented revenue was 30 million.'}],
                    [{'source': 3, 'quote': texts[1]}]]:
        invalid = deepcopy(payload)
        invalid['citation_quotes'] = records
        result = generate(invalid)
        assert result['outcome'] == 'refuse' and result['citation_error']
        assert result['citations'] == [] and '30 million' not in result['answer']
    chunks[0].evidence_spans[0].text = texts[1]
    assert generate(payload)['citation_error'] == 'Quote is absent or ambiguous across original sources'
    chunks[0].document_id = chunks[1].document_id
    assert generate(payload)['citations'] == ['quote_0']  # Same original document/version is safe.
    chunks[0].evidence_spans[0].kind = 'generated'
    chunks[1].evidence_spans[0].source_version = 'old'
    chunks.append(DocumentChunk(chunk_id='verified', document_id='v', source_version='v1', text=texts[0],
        evidence_spans=[EvidenceSpan(block_id='v', source_version='v1', char_start=0,
                                    char_end=len(texts[0]), text=texts[0])]))
    assert generate(payload)['citation_error'] == 'Quote is absent or ambiguous across original sources'
    for chunk in chunks:
        chunk.evidence_spans = []
    assert generate(payload)['citation_error'] == 'No verified original citation evidence'
