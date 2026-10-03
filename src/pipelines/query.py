"""
QueryPipeline — LangGraph state machine for the read side of RAG.

Why LangGraph instead of a linear LCEL chain?
  - We need branching (quick vs deep retrieval based on query type)
  - We need a refusal short-circuit when retrieval returns nothing
  - We want every node observable in LangSmith independently

The graph:

    [classify_query]
         │
         ├── (factual_lookup) ── [quick_retrieve] ──┐
         │                                          │
         └── (analytical) ────── [deep_retrieve] ───┤
                                                    │
                              [check_retrieval] ────┤
                                  │                 │
                          ┌───────┴───────┐         │
                          │               │         │
                  (no_results)        (has_results) │
                          │               │         │
                          ▼               ▼         │
                    [refuse]         [generate]     │
                          │               │         │
                          └───────┬───────┘         │
                                  │                 │
                                 END                │

Each node is a pure function of state → state. State is a TypedDict carrying
query, retrieved chunks, answer, citations, and a stage trace for debugging.
"""
from __future__ import annotations
import time
import re
from typing import TypedDict, Literal, Optional, Any
from langgraph.graph import StateGraph, END
from langsmith import traceable

from src.core.interfaces import BaseRetriever, BaseGenerator
from src.core.models import DocumentChunk
from src.observability import CostTracker


# =============================================================
# State
# =============================================================
class QueryState(TypedDict, total=False):
    query: str
    query_type: Literal["factual_lookup", "analytical"]
    candidates: list[DocumentChunk]
    chunks: list[DocumentChunk]
    answer: str
    citations: list[str]
    invalid_citations: list[int]
    refused: bool
    outcome: Optional[str]
    retrieval_latency_ms: float
    stages: list[str]                 # debug trace
    metadata: dict[str, Any]
    supplement_k: int
    research_request: Any
    research_snapshot: dict
    research_result: dict
    evidence_request: Any


_FACTUAL_KEYWORDS = (
    "what", "how much", "how many", "what was", "what is", "when did", "ratio", "percent",
    "amount", "value", "number"
)


def _classify_query(query: str) -> Literal["factual_lookup", "analytical"]:
    """Cheap heuristic — no LLM call, no cost. Adequate for the lab.
    
    Production: replace with a small LLM call or fine-tuned classifier.
    """
    q = query.lower().strip()
    # These requests need coverage across passages even when phrased briefly.
    if re.search(r"\b(?:outlook|trend|evolv\w*|growth|perform\w*|highlights?|risks?|compare\w*|drivers?|progress|rank\w*)\b", q):
        return "analytical"
    # Short queries that start with what/how/when → factual lookup
    if any(q.startswith(k) for k in _FACTUAL_KEYWORDS) and len(query.split()) < 12:
        return "factual_lookup"
    return "analytical"


# =============================================================
# Pipeline
# =============================================================
class QueryPipeline:
    """
    Orchestrates retriever + generator via a LangGraph state machine.
    
    Args:
        retriever: BaseRetriever (typically HybridRetriever)
        generator: BaseGenerator (typically RAGGenerator)
        quick_k: top-k for factual lookups (default 3)
        deep_k: top-k for analytical questions (default 8)
        cost_tracker: shared cost tracker
    """
    
    def __init__(
        self,
        retriever: BaseRetriever,
        generator: BaseGenerator,
        quick_k: int = 3,
        deep_k: int = 8,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self.retriever = retriever
        self.generator = generator
        self.quick_k = quick_k
        self.deep_k = deep_k
        self.cost_tracker = cost_tracker
        self.graph = self._build_graph()
    
    def _retrieve(self, query, k, supplement_k=0):
        start = time.perf_counter()
        if hasattr(self.retriever, "retrieve_with_candidates"):
            options = {"supplement_k": supplement_k} if supplement_k else {}
            result = self.retriever.retrieve_with_candidates(query, k=k, **options)
        else:
            result = {"chunks": self.retriever.retrieve(query, k=k), "candidates": []}
        result["retrieval_latency_ms"] = (time.perf_counter() - start) * 1000
        return result

    # ---- Nodes ----
    def _node_classify(self, state: QueryState) -> QueryState:
        qt = _classify_query(state["query"])
        return {
            **state,
            "query_type": qt,
            "stages": [*state.get("stages", []), f"classify→{qt}"],
        }
    
    def _node_quick_retrieve(self, state: QueryState) -> QueryState:
        details = self._retrieve(state["query"], self.quick_k, state.get("supplement_k", 0))
        chunks = details["chunks"]
        return {
            **state,
            **details,
            "stages": [*state.get("stages", []), f"quick_retrieve→{len(chunks)}"],
        }
    
    def _node_deep_retrieve(self, state: QueryState) -> QueryState:
        details = self._retrieve(state["query"], self.deep_k, state.get("supplement_k", 0))
        chunks = details["chunks"]
        return {
            **state,
            **details,
            "stages": [*state.get("stages", []), f"deep_retrieve→{len(chunks)}"],
        }
    
    def _node_generate(self, state: QueryState) -> QueryState:
        options = {"financial_evidence": True} if state.get("supplement_k") else {}
        result = self.generator.generate(state["query"], state.get("chunks", []), **options)
        return {
            **state,
            "answer": result["answer"],
            "citations": result.get("citations", []),
            "invalid_citations": result.get("invalid_citations", []),
            "refused": result.get("outcome") == "refuse" if result.get("outcome") else result.get("refused", False),
            "outcome": result.get("outcome"),
            "stages": [*state.get("stages", []), "generate",
                       *(["citation_guard→" + result["citation_error"]] if result.get("citation_error") else []),
                       *(["calculation_guard→" + result["calculation_error"]] if result.get("calculation_error") else [])],
            "metadata": {**state.get("metadata", {}), **{
                k: v for k, v in result.items() if k.startswith("n_")
            }},
        }
    
    def _node_refuse(self, state: QueryState) -> QueryState:
        return {
            **state,
            "answer": "I don't have enough information in the provided sources to answer that question.",
            "citations": [],
            "refused": True,
            "outcome": "refuse",
            "stages": [*state.get("stages", []), "refuse"],
        }

    def _node_research(self, state: QueryState) -> QueryState:
        if state.get('evidence_request') is not None:
            from src.financial.evidence import search_evidence
            result = search_evidence(state['evidence_request'], state['research_snapshot'])
        else:
            from src.financial.research import run_research
            result = run_research(state['research_request'], state['research_snapshot'])
        return {**state, 'research_result': result}
    
    # ---- Edges ----
    @staticmethod
    def _route_after_classify(state: QueryState) -> Literal["quick_retrieve", "deep_retrieve"]:
        return "quick_retrieve" if state["query_type"] == "factual_lookup" else "deep_retrieve"
    
    @staticmethod
    def _route_after_retrieve(state: QueryState) -> Literal["generate", "refuse"]:
        return "generate" if state.get("chunks") else "refuse"
    
    # ---- Build ----
    def _build_graph(self):
        g = StateGraph(QueryState)
        g.add_node("classify", self._node_classify)
        g.add_node("quick_retrieve", self._node_quick_retrieve)
        g.add_node("deep_retrieve", self._node_deep_retrieve)
        g.add_node("generate", self._node_generate)
        g.add_node("refuse", self._node_refuse)
        g.add_node('research', self._node_research)
        
        g.set_conditional_entry_point(lambda state: 'research' if state.get('research_request') is not None or state.get('evidence_request') is not None else 'classify',
                                      {'research': 'research', 'classify': 'classify'})
        g.add_conditional_edges(
            "classify", self._route_after_classify,
            {"quick_retrieve": "quick_retrieve", "deep_retrieve": "deep_retrieve"},
        )
        g.add_conditional_edges(
            "quick_retrieve", self._route_after_retrieve,
            {"generate": "generate", "refuse": "refuse"},
        )
        g.add_conditional_edges(
            "deep_retrieve", self._route_after_retrieve,
            {"generate": "generate", "refuse": "refuse"},
        )
        g.add_edge("generate", END)
        g.add_edge("refuse", END)
        g.add_edge('research', END)
        return g.compile()
    
    # ---- Public API ----
    @traceable(name="query_pipeline")
    def query(self, question: str, *, supplement_k: int = 0) -> dict[str, Any]:
        if type(supplement_k) is not int or not 0 <= supplement_k <= 8:
            raise ValueError("supplement_k must be an integer between 0 and 8")
        if self.cost_tracker is None:
            return self._query(question, supplement_k)
        with self.cost_tracker.request() as receipt:
            result = self._query(question, supplement_k)
            result["usage"] = receipt.report()
            return result

    def _query(self, question, supplement_k=0):
        initial = QueryState(query=question, stages=[], metadata={}, supplement_k=supplement_k)
        final = self.graph.invoke(initial)
        return {
            "query": question,
            "answer": final.get("answer", ""),
            "citations": final.get("citations", []),
            "invalid_citations": final.get("invalid_citations", []),
            "chunks": final.get("chunks", []),
            "candidates": final.get("candidates", []),
            "refused": final.get("refused", False),
            "outcome": final.get("outcome"),
            "retrieval_latency_ms": final.get("retrieval_latency_ms", 0),
            "stages": final.get("stages", []),
            "query_type": final.get("query_type"),
        }

    def research(self, request, snapshot):
        from src.financial.research import ResearchRequest
        request = ResearchRequest.model_validate(request)
        return self.graph.invoke({'research_request': request, 'research_snapshot': snapshot})['research_result']

    def evidence(self, request, snapshot):
        from src.financial.evidence import EvidenceSearchRequest
        request = EvidenceSearchRequest.model_validate(request)
        return self.graph.invoke({'evidence_request': request, 'research_snapshot': snapshot})['research_result']
    
    def draw_mermaid(self) -> str:
        """Return the graph as Mermaid markup — useful for notebook display."""
        try:
            return self.graph.get_graph().draw_mermaid()
        except Exception:
            return "graph TD\n  A[classify] --> B[retrieve]\n  B --> C[generate]\n  C --> D[END]"
