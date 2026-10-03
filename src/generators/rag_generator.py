"""
RAGGenerator — Stage 6: query + retrieved chunks → grounded answer with citations.

Design choices worth knowing in interviews:

  1. Citation format: we tag each chunk with [^1], [^2], ... in the prompt and
     ask the model to include those tags. Then we resolve them back to chunk_ids
     in the response. This is the simplest scheme that lets users click back to
     source. Production systems use structured outputs (JSON tool-calling) for
     stronger guarantees — see 04_generation notebook for the upgrade path.

  2. Refusal handling: if no chunks retrieved, we DON'T call the LLM. We return
     a fixed refusal answer. That saves cost AND prevents the LLM from hallucinating
     to fill the void.

  3. Lazy LLM init: ChatOpenAI is constructed on first call, not at __init__.
     This makes the module import-safe without an API key.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from src.core.interfaces import BaseGenerator
from src.core.models import DocumentChunk
from src.core.config import settings
from src.observability import CostTracker


_BASELINE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a financial analyst assistant. Your task is to answer questions \
based ONLY on the provided context. Never use outside knowledge.

Rules:
1. **Verify the question matches the context** before answering. If the user asks about \
"Q4 2025 net income" but the context only shows "Q4 2024" or only mentions a specific \
segment's net income (e.g., Consumer Banking), DO NOT use that number for the bank-wide \
answer. Numbers from the wrong period or wrong scope are worse than refusing.
The company must also match. Another company's evidence cannot answer a named-company question.

2. **Refusal protocol**: If the requested fact is unsupported, refuse directly and state
what source is missing. Do not include unrelated companies' figures, alternative-period
numbers, factual claims or citations in a refusal. Use clarification for an ambiguous scope.

3. **Citations**: Cite every factual claim using [^1], [^2], etc. matching the source \
numbers below. When quoting a number, ALWAYS cite where it came from.

4. **Use specific numbers and direct quotes when available**. Do not paraphrase numbers. \
If a value appears as "$5.4 billion" in context, write "$5.4 billion", not "5.4B" or \
"about 5 billion".

5. Generated descriptions are retrieval aids; original table rows and source text control numerical claims. Do not treat a generated image description as verified original text.

6. Return one JSON object with exactly two fields: "outcome" and "answer".
Outcome must be "answer", "qualified_answer", "clarify", or "refuse".
Use "refuse" when the requested fact is unsupported, "clarify" when the user must
specify period/scope/basis, and "qualified_answer" when a supported answer needs
explicit limitations. Never hide an unsupported assertion inside refusal prose.
The answer field contains the user-facing prose and [^N] citations.

7. Keep the answer concise — 1-3 sentences for fact lookups, up to 5 sentences \
for analytical questions."""),
    ("human", """Context (numbered sources):
{context}

Question: {question}

Response (JSON with outcome and cited answer):"""),
])



_FINANCIAL_EVIDENCE_RULES = """Return one JSON object with "outcome", "answer", "citation_quotes", and optional "calculations".
For EVERY cited source number, provide a citation_quotes entry with "source" (that
number) and "quote" (verbatim original supporting text, including the actual row
label and values when numeric). Supply multiple quotes when a source supports several
claims. Copy substantive original text, not a number alone, a generated header or your
paraphrase. Source numbers will be checked against those original quotes before output.
Example: "citation_quotes": [{"source": 1, "quote": "verbatim original sentence"}].
The source must be an integer, never a string such as "[Source 1]".
Use an empty citation_quotes list for clarification/refusal. Do not report a financial
value if its supporting row, period column and unit cannot be identified.
For a derived difference, percentage-point change or relative growth, do not write a
hand-computed result. Use an answer placeholder {calc:0} (zero-based calculation
index) and a calculations entry with operation "difference", "percentage_point_change"
or "growth", plus "start" and "end" operands. Each operand has "source" (source number),
"quote" (exact original text containing the value), "value_text" (literal numeric
token, commas allowed), and "company", "metric", "period", "period_kind" ("quarterly"
or "annual"), "scope", "basis", "unit". For operating counts, basis describes the
original operating definition instead of GAAP. These labels
must appear in the original source evidence. The operands must describe the same
company/scope/basis/unit and period kind. Changes and growth require the same metric
in distinct explicit periods; "difference" also supports distinct metrics in one
period (for example, vehicle production minus deliveries). Never change both metric
and period in one calculation. Use unit "%" for percentage-point changes.
Every operation computes end minus start; growth divides that change by start.
Every placeholder requires exactly one matching calculations entry. Never return
a placeholder with an omitted or empty calculations array. Source-reported growth
rates can be quoted directly and ranked when their periods/definitions are comparable;
do not create a calculation merely to repeat those reported rates.
An exact source-stated derived result may be quoted and cited directly; other derived
claims require a calculation placeholder, including prose about the change's direction.
If these operands are unavailable, qualify the answer
without a derived result. Server-side arithmetic checks do not prove a model's
association of a table row with its period column; choose the supporting rows carefully.
"""


_RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a financial analyst assistant. Your task is to answer questions \
based ONLY on the provided context. Never use outside knowledge.

Rules:
1. **Choose the outcome before filling evidence gaps.** Use "clarify" when a numerical comparison
needs a reporting period, revenue definition, accounting basis (GAAP/non-GAAP), or
consolidated/segment scope. "Most recent quarter" does not establish a common period
across companies. Ask the specific missing questions even when comparison figures
are absent; do not rank companies or invent comparability. When the requested segment
metric is absent but the same company's consolidated metric is present, ask whether
the user wants that supported scope or can provide segment evidence. Never silently
substitute it. A clarification can consist entirely of questions without factual claims.
Ask all unresolved scope, basis and period questions together. A qualitative comparison
of supported but differently measured trajectories can be a "qualified_answer" with
explicit limits; do not require a common numeric metric to compare source statements.

2. **Refusal protocol**: Refuse a fact about an unsupported company, an explicitly
requested but unavailable period/future event, or external current data. Another
company's evidence cannot answer a named-company question. For an unambiguous request,
use "qualified_answer" if some requested evidence is supported and clearly identify
the unanswered parts; refuse when none is supported. Missing evidence alone does not
make a specified period ambiguous. Do not include unrelated companies' figures,
alternative-period numbers, factual claims or citations in a refusal.
Use "answer" when the requested facts or source-reported drivers are completely
supported. A reporting-period label alone is not a qualification. Use "qualified_answer"
for an actual coverage/comparability limitation or an interpretation not established
by the evidence, such as what a production-delivery gap implies about inventory.

3. **Citations and arithmetic**: Cite every factual claim using [^1], [^2], etc.
The cited source itself must contain the supporting row/text; a title or caution card
cannot support a number found in another source. Before using any value, check its
company, row label, column period, unit, and consolidated/segment and GAAP/non-GAAP
basis. For a change, ratio or ranking, require all operands on a comparable basis,
cite each operand, and verify the arithmetic and direction before stating the result.
Do not guess missing operands or state a tentative figure and then retract it.
Read each table row's own label: an adjacent automotive revenue row does not make
a "Total GAAP gross margin" row automotive margin. Keep consolidated gross margin,
automotive margin, and automotive margin excluding credits distinct.

4. **Use specific numbers and direct quotes when available**. Do not paraphrase numbers. \
If a value appears as "$5.4 billion" in context, write "$5.4 billion", not "5.4B" or \
"about 5 billion".

5. Generated descriptions are retrieval aids; original table rows and source text control numerical claims. Do not treat a generated image description as verified original text.
Separate the filing's reporting period from the date of each event. A post-quarter
event in a quarterly update is not a result achieved during that quarter; omit it
from quarter-specific operating results or explicitly label it as subsequent context.

6. Return one JSON object with "outcome" and "answer".
{financial_evidence_rules}
Outcome must be "answer", "qualified_answer", "clarify", or "refuse".
Use "refuse" when the requested fact is unsupported, "clarify" when the user must
specify period/scope/basis, and "qualified_answer" when a supported answer needs
explicit limitations. Never hide an unsupported assertion inside refusal prose.
The answer field contains the user-facing prose and [^N] citations.

7. Keep the answer concise — 1-3 sentences for fact lookups, up to 5 sentences \
for analytical questions."""),
    ("human", """Context (numbered sources):
{context}

Question: {question}

Response (JSON with outcome and cited answer):"""),
])


_NO_RESULT_ANSWER = (
    "I could not find any relevant information in the provided sources to answer that question. "
    "No documents were retrieved — please check whether the relevant document is indexed."
)


def _original_spans(chunk):
    return [s for s in chunk.evidence_spans if s.kind == "original"
            and chunk.source_version and s.source_version == chunk.source_version]


def clarify_financial_query(query, chunks):
    """Ask about ambiguous financial scope only for a confirmed, named corpus company."""
    q = query.casefold()
    names = {str(m[field]).strip() for chunk in chunks
             if (m := chunk.metadata.get("confirmed_source_metadata", {})).get("review_status") == "confirmed"
             for field in ("company_name", "company_id") if m.get(field)}
    if not any(name and re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", q) for name in names):
        return None
    basis = bool(re.search(r"\b(?:gaap|non-gaap)\b", q))
    if re.search(r"\b(?:automotive|segment)\s+(?:gross\s+)?margins?\b", q) and not basis:
        return "Do you want automotive/segment or consolidated gross margin, on a GAAP or non-GAAP basis? Which periods should I compare?"
    if not re.search(r"\b(?:larger|largest|higher|highest|lower|lowest|compare|versus|vs)\b", q):
        return None
    margin = bool(re.search(r"\bgross\s+margins?\b", q))
    revenue = bool(re.search(r"\brevenues?\b", q))
    if not (margin or revenue):
        return None
    dimensions = []
    if not re.search(r"\b(?:19|20)\d{2}\b", q) or not re.search(r"\bQ[1-4]\b|\bquarter\b|\byear\b|\bFY\b", query, re.I):
        dimensions.append("reporting period(s)")
    if revenue and not re.search(r"\b(?:total|net|consolidated|segment)\s+revenues?\b", q):
        dimensions.append("revenue definition")
    if margin:
        if not basis:
            dimensions.append("GAAP or non-GAAP basis")
        if not re.search(r"\b(?:consolidated|company-wide|automotive|segment)\b", q):
            dimensions.append("consolidated or segment scope")
    return "Which " + ", ".join(dimensions) + " should I use for the comparison?" if dimensions else None


def _build_baseline_context(chunks: list[DocumentChunk]) -> tuple[str, dict[int, str]]:
    """
    Build the numbered context block. Returns (context_string, num_to_chunk_id).
    """
    parts = []
    num_to_chunk_id: dict[int, str] = {}
    for i, chunk in enumerate(chunks, start=1):
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else ""
        pages = sorted({s.page_number for s in getattr(chunk, "evidence_spans", []) if s.page_number})
        page = f" (pages {', '.join(map(str, pages))})" if pages else (f" (p. {chunk.page_number})" if chunk.page_number else "")
        identity = f" document={chunk.document_id} version={getattr(chunk, 'source_version', None) or 'legacy/unverified'}"
        header = f"[Source {i}]" + (f" {heading}" if heading else "") + page + identity
        parts.append(f"{header}\n{chunk.text}")
        num_to_chunk_id[i] = chunk.chunk_id
    return "\n\n".join(parts), num_to_chunk_id



def _build_context(chunks: list[DocumentChunk]) -> tuple[str, dict[int, str]]:
    """
    Build the numbered context block. Returns (context_string, num_to_chunk_id).
    """
    parts = []
    num_to_chunk_id: dict[int, str] = {}
    for i, chunk in enumerate(chunks, start=1):
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else ""
        pages = sorted({s.page_number for s in getattr(chunk, "evidence_spans", []) if s.page_number})
        page = f" (pages {', '.join(map(str, pages))})" if pages else (f" (p. {chunk.page_number})" if chunk.page_number else "")
        identity = f" document={chunk.document_id} version={getattr(chunk, 'source_version', None) or 'legacy/unverified'}"
        originals = _original_spans(chunk)
        if originals:
            fragments, seen, previous_page = [], set(), None
            for span in originals:
                key = (span.page_number, span.text)
                if key in seen:
                    continue
                seen.add(key)
                if span.page_number and span.page_number != previous_page:
                    fragments.append(f"[Original page {span.page_number}]")
                fragments.append(span.text)
                previous_page = span.page_number
            body = "\n".join(fragments)
            header = f"[Source {i}]" + page + identity
        else:
            label = ("Generated retrieval aid; no verified original evidence" if any(s.kind == "generated" for s in chunk.evidence_spans)
                     else "Unverified/stale retrieval text" if chunk.evidence_spans else "Legacy/unverified retrieval text")
            body = f"[{label}]\n{chunk.text}"
            header = f"[Source {i}]" + (f" {heading}" if heading else "") + page + identity
        parts.append(f"{header}\n{body}")
        num_to_chunk_id[i] = chunk.chunk_id
    return "\n\n".join(parts), num_to_chunk_id


def _extract_citations(answer: str, num_to_chunk_id: dict[int, str]) -> list[str]:
    """Find [^N] citations in the answer and resolve to chunk_ids."""
    nums = [int(n) for n in re.findall(r"\[\^(\d+)\]", answer)]
    seen: set[str] = set()
    out: list[str] = []
    for n in nums:
        cid = num_to_chunk_id.get(n)
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


class CalculationOperand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: int = Field(gt=0)
    quote: str = Field(min_length=1)
    value_text: str = Field(min_length=1)
    company: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    period: str = Field(min_length=1)
    period_kind: Literal["quarterly", "annual"]
    scope: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    unit: str = Field(min_length=1)


class Calculation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["difference", "percentage_point_change", "growth"]
    start: CalculationOperand
    end: CalculationOperand


class CitationQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: int = Field(gt=0, strict=True)
    quote: str = Field(min_length=1)


def _bind_citation_quotes(answer, quotes, calculations, chunks):
    """Bind footnotes to verbatim originals; this does not judge prose entailment."""
    if not any(_original_spans(chunk) for chunk in chunks):
        raise ValueError("No verified original citation evidence")
    used = {int(n) for n in re.findall(r"\[\^(\d+)\]", answer)}
    if not used:
        raise ValueError("Supported answers require original-source citations")
    records = [(record.source, record.quote) for record in quotes]
    records += [(operand.source, operand.quote) for calc in calculations for operand in (calc.start, calc.end)]
    resolved = {}
    for source, quote in records:
        if source not in used or not 1 <= source <= len(chunks):
            raise ValueError("Quote source does not match an issued citation")
        if len(re.findall(r"[^\W\d_]+", quote, flags=re.UNICODE)) < 2:
            raise ValueError("Citation support needs substantive text, not a number")
        normalized = " ".join(quote.split())
        matches = [index for index, chunk in enumerate(chunks, 1)
                   if normalized in " ".join(" ".join(s.text for s in _original_spans(chunk)).split())]
        identities = {(chunks[index - 1].document_id, chunks[index - 1].source_version) for index in matches}
        if len(identities) != 1:
            raise ValueError("Quote is absent or ambiguous across original sources")
        # Exact quote + a unique original document/version is independent location proof.
        target = source if source in matches else matches[0]
        resolved.setdefault(source, set()).add(target)
    if used != set(resolved):
        raise ValueError("Every issued citation requires an original supporting quote")
    return re.sub(r"\[\^(\d+)\]", lambda m: "".join(f"[^{n}]" for n in sorted(resolved[int(m[1])])), answer)


def _render_calculations(answer, calculations, chunks):
    """Check original quoted operands, then calculate; semantic table binding still needs review."""
    placeholders = re.findall(r"\{calc:(\d+)\}", answer)
    if answer.count("{calc:") != len(placeholders) or sorted(map(int, placeholders)) != list(range(len(calculations))):
        raise ValueError("Every calculation requires exactly one answer placeholder")
    for index, calc in enumerate(calculations):
        values = []
        for operand in (calc.start, calc.end):
            if operand.source > len(chunks):
                raise ValueError("Calculation source is absent")
            chunk = chunks[operand.source - 1]
            originals = [s.text for s in _original_spans(chunk)]
            if not any(operand.quote in original for original in originals):
                raise ValueError("Calculation quote lacks original support")
            support = " ".join(originals).casefold()
            if not all(getattr(operand, field).strip() and re.search(
                    r"(?<![\w-])" + re.escape(getattr(operand, field).strip().casefold()) + r"(?![\w-])", support)
                       for field in ("company", "metric", "period", "scope", "basis")) or not operand.unit.strip() or operand.unit.strip().casefold() not in support:
                raise ValueError("Calculation labels lack original support")
            if not re.search(r"\b(?:19|20)\d{2}\b", operand.period):
                raise ValueError("Calculation period requires an explicit year")
            quarterly = bool(re.search(r"\bQ[1-4]\b|\bquarter", operand.period, re.I))
            annual = bool(re.search(r"\bFY\b|\byear\b|\bannual\b|\b(?:12|twelve)\s+months\b", operand.period, re.I))
            cumulative = bool(re.search(r"\bYTD\b|year[- ]to[- ]date|\b(?:6|9|12|six|nine|twelve)[- ]months?\b", operand.period, re.I))
            if (operand.period_kind == "quarterly" and (not quarterly or cumulative)) or (operand.period_kind == "annual" and (quarterly or not annual)):
                raise ValueError("Period kind lacks explicit support")
            if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", operand.value_text):
                raise ValueError("Invalid numeric operand")
            if not re.search(r"(?<![\w.,+-])" + re.escape(operand.value_text) + r"(?![\w.,])", operand.quote):
                raise ValueError("Operand value lacks quoted support")
            value = Decimal(operand.value_text.replace(",", ""))
            if not value.is_finite():
                raise ValueError("Nonfinite operand")
            values.append(value)
        if any(getattr(calc.start, f).strip().casefold() != getattr(calc.end, f).strip().casefold()
               for f in ("company", "scope", "basis", "unit", "period_kind")):
            raise ValueError("Incomparable calculation operands")
        same_metric = calc.start.metric.strip().casefold() == calc.end.metric.strip().casefold()
        same_period = calc.start.period.strip().casefold() == calc.end.period.strip().casefold()
        if same_metric == same_period or (calc.operation != "difference" and not same_metric):
            raise ValueError("A calculation can change only metric or period")
        delta = values[1] - values[0]
        unit = calc.start.unit.strip()
        if calc.operation == "percentage_point_change":
            if unit != "%":
                raise ValueError("Percentage-point change requires percentage operands")
            unit = "percentage points"
        elif calc.operation == "growth":
            if values[0] <= 0:
                raise ValueError("Growth requires a positive starting value")
            delta = (delta / values[0] * 100).quantize(Decimal("0.01"))
            unit = "%"
        suffix = unit if unit == "%" else f" {unit}"
        rendered = f"{delta.normalize():+f}{suffix} [^{calc.start.source}] [^{calc.end.source}]"
        answer = answer.replace(f"{{calc:{index}}}", rendered)
    return answer


class AnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["answer", "qualified_answer", "clarify", "refuse"]
    answer: str = Field(min_length=1)
    calculations: list[Calculation] = Field(default_factory=list)
    citation_quotes: list[CitationQuote] = Field(default_factory=list, max_length=32)


class RAGGenerator(BaseGenerator):
    """
    Citation-aware answer generation.
    
    Args:
        model: LLM model name (default: settings.llm_model = gpt-5-mini)
        temperature: 0 for factual answers (default)
        cost_tracker: pass a tracker to record API costs
        refuse_on_empty: if True, returns a fixed refusal when no chunks (default: True)
    """
    
    name = "rag_generator"
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.0,
        cost_tracker: Optional[CostTracker] = None,
        refuse_on_empty: bool = True,
    ):
        self.model = model or settings.llm_model
        self.temperature = temperature
        self.cost_tracker = cost_tracker
        self.refuse_on_empty = refuse_on_empty
        self._llm = None
    
    def _get_llm(self):
        if self._llm is None:
            from src.core.config import make_chat_llm
            self._llm = make_chat_llm(self.model, temperature=self.temperature,
                                      model_kwargs={"response_format": {"type": "json_object"}})
        return self._llm
    
    @traceable(name="rag_generate")
    def generate(self, query: str, chunks: list[DocumentChunk], *, financial_evidence: bool = False) -> dict[str, Any]:
        if not chunks and self.refuse_on_empty:
            return {
                "answer": _NO_RESULT_ANSWER,
                "citations": [],
                "n_sources_used": 0,
                "refused": True,
                "outcome": "refuse",
            }

        clarification = clarify_financial_query(query, chunks)
        if clarification:
            return {"answer": clarification, "citations": [], "invalid_citations": [],
                    "n_sources_used": 0, "n_sources_retrieved": len(chunks),
                    "refused": False, "outcome": "clarify", "calculation_error": None}
        
        context, num_to_chunk_id = (_build_context if financial_evidence else _build_baseline_context)(chunks)
        prompt_messages = (_RAG_PROMPT if financial_evidence else _BASELINE_PROMPT).format_messages(
            context=context, question=query, financial_evidence_rules=_FINANCIAL_EVIDENCE_RULES)
        
        result = self._get_llm().invoke(prompt_messages)
        if self.cost_tracker:
            self.cost_tracker.record_response("rag_generate", self.model, result)
        # Invalid envelopes fail explicitly; never guess an outcome from prose.
        evidence_error = None
        try:
            payload = AnswerPayload.model_validate_json(result.content.strip())
        except ValidationError as exc:
            if not all(error['loc'] and error['loc'][0] in {'citation_quotes', 'calculations'}
                       for error in exc.errors()):
                raise
            evidence_error = 'Malformed citation/calculation evidence'
            payload = AnswerPayload(outcome='refuse', answer='Invalid evidence.')
        if not payload.answer.strip():
            raise ValueError("Generator returned an empty answer")
        answer = payload.answer.strip()
        outcome = payload.outcome
        calculation_error = None
        citation_error = evidence_error
        try:
            if payload.calculations and outcome not in {"answer", "qualified_answer"}:
                raise ValueError("Calculations require a supported answer outcome")
            answer = _render_calculations(answer, payload.calculations, chunks)
        except (ValueError, InvalidOperation) as exc:
            calculation_error = str(exc)
            outcome = "refuse"
        if financial_evidence and (outcome in {"answer", "qualified_answer"} or
                                   (outcome == "clarify" and re.search(r"\[\^\d+\]", answer))):
            try:
                answer = _bind_citation_quotes(answer, payload.citation_quotes, payload.calculations, chunks)
            except ValueError as exc:
                citation_error = str(exc)
                outcome = "refuse"
        if outcome == "refuse":
            # A model refusal must not smuggle unrelated or unsupported facts into prose.
            answer = "I don't have enough information in the provided sources to answer that question. Please add a source covering the requested company, period, or fact."
        citations = _extract_citations(answer, num_to_chunk_id)

        return {
            "answer": answer,
            "citations": citations,
            "invalid_citations": [int(n) for n in re.findall(r"\[\^(\d+)\]", answer) if int(n) not in num_to_chunk_id],
            "n_sources_used": len(citations),
            "n_sources_retrieved": len(chunks),
            "refused": outcome == "refuse",
            "outcome": outcome,
            "calculation_error": calculation_error,
            "citation_error": citation_error,
        }
