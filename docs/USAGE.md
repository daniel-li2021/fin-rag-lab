# Usage, outcomes and cost reporting

Generation returns a validated JSON envelope with `outcome` (`answer`, `qualified_answer`, `clarify`, `refuse`) and cited `answer` prose. Invalid/empty envelopes fail explicitly; no prose substring guesses an outcome. Empty retrieval returns a structured refusal without a generation call. `refused` remains a compatibility boolean for `outcome=refuse`. A clarification is distinct from a refusal.

Optional claim verification now runs on refusal/clarification prose too, extracting concrete world/financial claims while excluding the refusal or request for clarification itself. Malformed verifier JSON is unsupported, never inferred as entailed from words in the response. Benchmark outcome-label agreement is reported separately from correctness with zero unsupported/refuted assertions; without verification, assertion-based correctness remains undefined. Neither an outcome label nor a model judge alone proves financial correctness. Numeric/period/scope and citation-support review still use the explicit benchmark labels/rubrics.

`CostTracker.request()` produces a unique receipt, isolated with ContextVars and protected aggregate updates. Nested scopes include their own work; sequential/concurrent requests do not inherit one another's usage. LangGraph worker context propagation is covered by an offline test. Service query latency and usage include optional verification; retrieval latency is reported separately. Ingestion totals include caption **and embedding** calls; per-document caption reports and cache hits have their own receipts. Indexed document cost summaries represent caption work, while the build's receipt includes shared embedding batches.

Raw usage records retain configured/response model, provider usage payload, input/output totals, reasoning detail, stage, price snapshot and cost estimate. Reasoning tokens are already included in completion/output totals and are never added again. A reported zero remains zero. Missing usage is unknown rather than a character-count estimate. Unknown prices or any unpriced call make total/stage/model cost null; `priced_subtotal_usd` is only the known subtotal. UI/CLI show unknown rather than zero or failing number formatting.

Prices are a **configured estimate**, not verified current billing rates. Existing approximate settings remain unchanged. Inject an explicit `CostTracker(pricing=...)` snapshot when exact experiment prices are needed. Cached-input/vision discounts or provider-specific adjustments are not silently inferred; raw details remain available for later repricing. The legacy manual flat-image method is explicitly marked as an estimate; application captioning uses actual response usage or unknown.

Embedding HTTP response hooks capture real per-batch usage before LangChain discards it, for synchronous/asynchronous calls, inside the existing cache. Cache hits record no call. Retrieval query embeddings and Ragas judge embeddings are included. The hooks persist usage/model only, never response vectors or request text. Generator, captioner, verifier and Ragas chat callbacks share one usage extractor. The persistent registry and runtime durable request logs remain later work; evaluation artifacts are the durable receipts in this batch.

## Benchmark artifacts

`run_benchmark.py` records request receipts/configuration with each flushed result. `--verify` enables assertion checks; `--ragas` adds optional secondary judge work, saved separately as `evaluation_usage` so online query cost/latency are not inflated by offline judging. Judge embeddings default independently to `text-embedding-3-small` and can be frozen explicitly with `--judge-embedding-model`. Refusal/clarification labels skip undefined Ragas answerability judging. Summaries report token/call totals, unknown cost calls, receipt/metric denominators, p50/p95 latency (linear interpolation) and unknown mean cost when any query is unpriced. NaN metrics persist as null.

New captures reject legacy evidence revisions and runtime/build embedding-model mismatch before querying; rebuilds remain explicit. Manifests hash vector artifacts as well as metadata/pickles and record installed dependency versions, reasoning configuration and price snapshot. Read-only replay needs no index or model calls. Existing `run_eval.py` uses the versioned overlay, saves per-question query/outcome/usage/config JSON in CSV and a `.csv.usage.json` receipt/config sidecar, and reports metric denominators. For controlled experiments, prefer the full benchmark manifest rather than the diagnostic CSV.

The notebook's OOC scoring now requires a structured refusal plus zero unsupported/refuted assertions. Only that changed cell's historical output was cleared; no notebook or paid benchmark was rerun.

```sh
python -m pytest tests/unit/test_usage.py tests/unit/test_benchmark.py tests/unit/test_evaluators.py tests/unit/test_generator_query.py tests/unit/test_rag_service.py tests/integration/test_api.py -q
```

Run tests from the repository root with `python -m pytest`; CI uses the same module invocation. The bare `pytest` console script can omit the repository from Python's import path and fail to import `src` during collection.
