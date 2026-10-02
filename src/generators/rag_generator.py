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
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from src.core.interfaces import BaseGenerator
from src.core.models import DocumentChunk
from src.core.config import settings
from src.observability import CostTracker


_RAG_PROMPT = ChatPromptTemplate.from_messages([
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


_NO_RESULT_ANSWER = (
    "I could not find any relevant information in the provided sources to answer that question. "
    "No documents were retrieved — please check whether the relevant document is indexed."
)


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
        header = f"[Source {i}]" + (f" {heading}" if heading else "") + page + identity
        parts.append(f"{header}\n{chunk.text}")
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


class AnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["answer", "qualified_answer", "clarify", "refuse"]
    answer: str = Field(min_length=1)


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
    def generate(self, query: str, chunks: list[DocumentChunk]) -> dict[str, Any]:
        if not chunks and self.refuse_on_empty:
            return {
                "answer": _NO_RESULT_ANSWER,
                "citations": [],
                "n_sources_used": 0,
                "refused": True,
                "outcome": "refuse",
            }
        
        context, num_to_chunk_id = _build_context(chunks)
        prompt_messages = _RAG_PROMPT.format_messages(context=context, question=query)
        
        result = self._get_llm().invoke(prompt_messages)
        if self.cost_tracker:
            self.cost_tracker.record_response("rag_generate", self.model, result)
        # Invalid envelopes fail explicitly; never guess an outcome from prose.
        payload = AnswerPayload.model_validate_json(result.content.strip())
        if not payload.answer.strip():
            raise ValueError("Generator returned an empty answer")
        answer = payload.answer.strip()
        if payload.outcome == "refuse":
            # A model refusal must not smuggle unrelated or unsupported facts into prose.
            answer = "I don't have enough information in the provided sources to answer that question. Please add a source covering the requested company, period, or fact."
        citations = _extract_citations(answer, num_to_chunk_id)

        return {
            "answer": answer,
            "citations": citations,
            "invalid_citations": [int(n) for n in re.findall(r"\[\^(\d+)\]", answer) if int(n) not in num_to_chunk_id],
            "n_sources_used": len(citations),
            "n_sources_retrieved": len(chunks),
            "refused": payload.outcome == "refuse",
            "outcome": payload.outcome,
        }
