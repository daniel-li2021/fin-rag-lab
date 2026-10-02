"""
Ragas-based evaluation. Wraps the 4 core RAG metrics:

  - faithfulness:        does the answer come from the retrieved context?
                         (catches hallucinations)
  - answer_relevancy:    does the answer address the question?
                         (catches off-topic answers)
  - context_precision:   are the retrieved chunks relevant? (signal/noise of retrieval)
  - context_recall:      did we retrieve everything needed?
                         (requires ground_truth answer)

Usage in 05_evaluation:
    evaluator = RagasEvaluator()
    df = evaluator.evaluate(qa_pipeline, golden_set)
    print(df.describe())
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional, Callable
import json

from src.core.config import settings


class RagasEvaluator:
    """Lightweight wrapper around ragas.evaluate() with our pipeline's contract."""
    
    def __init__(
        self,
        metrics: Optional[list[str]] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        cost_tracker: Optional[Any] = None,
    ):
        self.metric_names = metrics or [
            "faithfulness", "answer_relevancy", "context_precision", "context_recall",
        ]
        self.llm_model = llm_model or settings.judge_model
        self.embedding_model = embedding_model or settings.embedding_model
        self.cost_tracker = cost_tracker

    def _load_metrics(self):
        """Lazy import — keeps the module import-safe without ragas installed."""
        from ragas.metrics import (
            faithfulness, answer_relevancy, context_precision, context_recall,
        )
        registry = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }
        return [registry[n] for n in self.metric_names if n in registry]

    def evaluate(
        self,
        query_fn: Callable[[str], dict[str, Any]],
        golden_set: list[dict[str, Any]],
        verbose: bool = True,
    ):
        """
        Run query_fn on each example, then evaluate with Ragas.

        Args:
            query_fn: callable taking question str -> returns dict with at least
                      {"answer": str, "chunks": list[DocumentChunk]} or
                      {"answer": str, "contexts": list[str]}
            golden_set: list of dicts with keys: question, ground_truth (optional)

        Returns: pandas.DataFrame with one row per example + metric columns
        """
        from src.evaluators.benchmark import serializable
        from ragas import evaluate
        from datasets import Dataset
        import pandas as pd

        rows = []
        for i, ex in enumerate(golden_set):
            q = ex["question"]
            if verbose:
                print(f"  [{i+1}/{len(golden_set)}] {q[:60]}{'...' if len(q) > 60 else ''}")
            result = query_fn(q)

            # Resolve contexts (chunks) -> list[str]
            if "contexts" in result:
                contexts = result["contexts"]
            elif "chunks" in result:
                contexts = [c["text"] if isinstance(c, dict) else c.text for c in result["chunks"]]
            else:
                contexts = []

            rows.append({
                "question": q,
                "answer": result.get("answer", ""),
                "contexts": contexts,
                "ground_truth": ex.get("ground_truth", ""),
                "category": ex.get("category", ""),
                "id": ex.get("id", ""),
                "expected_outcome": ex.get("expected_outcome", "refuse" if ex.get("category") == "out_of_corpus" else "answer"),
                "outcome": result.get("outcome"),
                "query_result_json": json.dumps(serializable(result)),
            })

        df = pd.DataFrame(rows)
        for name in self.metric_names:
            df[name] = float("nan")
        eligible = [i for i, row in enumerate(rows) if row["expected_outcome"] not in ("refuse", "clarify")]
        if not eligible:
            return df
        ds = Dataset.from_list([{k: rows[i][k] for k in ("question", "answer", "contexts", "ground_truth")} for i in eligible])
        if verbose:
            print(f"\nRunning Ragas on {len(ds)} supported examples...")

        # Wire our judge model + embedding model into ragas.evaluate so that
        # Ragas actually uses what we configured (otherwise it falls back to
        # its internal default, which may be a deprecated model).
        # make_chat_llm handles the GPT-5/o-series temperature constraint.
        from src.core.config import make_chat_llm
        from src.observability.embeddings import make_tracked_embeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper

        # Build judge LLM. If we have a cost tracker, attach a callback that
        # captures token usage from every call so Ragas's costs flow into it.
        callbacks = []
        if self.cost_tracker is not None:
            callbacks = [_RagasCostCallback(self.cost_tracker, self.llm_model)]

        chat_llm = make_chat_llm(self.llm_model, temperature=0, callbacks=callbacks)
        judge_llm = LangchainLLMWrapper(chat_llm)
        judge_emb = LangchainEmbeddingsWrapper(make_tracked_embeddings(self.embedding_model, self.cost_tracker))

        result = evaluate(
            ds,
            metrics=self._load_metrics(),
            llm=judge_llm,
            embeddings=judge_emb,
        )
        scored = result.to_pandas()
        if len(scored) != len(eligible):
            raise ValueError("Ragas returned a different number of rows")
        for name in self.metric_names:
            if name in scored:
                df.loc[eligible, name] = scored[name].to_numpy()
        return df

    @staticmethod
    def load_golden_set(path: str | Path) -> list[dict]:
        """Load a JSONL golden set."""
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]


from langchain_core.callbacks import BaseCallbackHandler


class _RagasCostCallback(BaseCallbackHandler):
    """LangChain callback handler that captures token usage from every chat
    call Ragas makes via its judge LLM, and routes it into our CostTracker.

    Inherits from BaseCallbackHandler because pydantic v2 validation on
    ChatOpenAI's `callbacks` field rejects duck-typed objects.
    """

    ignore_chain = True
    ignore_agent = True
    ignore_retry = True
    ignore_retriever = True
    ignore_custom_event = True

    def __init__(self, cost_tracker, model: str):
        super().__init__()
        self.cost_tracker = cost_tracker
        self.model = model

    # Called when an LLM/chat call ends; `response` is a LangChain LLMResult
    def on_llm_end(self, response, *, run_id=None, parent_run_id=None, **kwargs):
        try:
            generations = getattr(response, "generations", []) or []
            for gen_list in generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg is not None:
                        self.cost_tracker.record_response("ragas_judge", self.model, msg)
        except Exception as exc:
            # Keep the evaluation running, but never hide a failed usage capture.
            self.cost_tracker.record_llm("ragas_judge", self.model, None, None,
                                         raw_usage={"capture_error": type(exc).__name__},
                                         usage_source="unavailable")

    # Required no-op stubs so LangChain doesn't complain on dispatch
    def on_llm_start(self, *a, **kw): pass
    def on_chat_model_start(self, *a, **kw): pass
    def on_llm_new_token(self, *a, **kw): pass
    def on_llm_error(self, *a, **kw): pass
