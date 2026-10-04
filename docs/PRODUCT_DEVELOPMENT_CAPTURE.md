# Authentic development capture

This is a local, reviewed development prototype. The planner remains disabled; public/cloud deployment and general authentic-accuracy claims remain held. Named **Codex** reviews are development evidence, not independent human release review.

## Frozen original evidence and labels

The persistent local corpus contains 22 ready official AMD, Tesla and Wells Fargo reports/decks. Reviewed windows preserve original physical pages and issuer-specific fiscal dates. The 168 immutable fact cards bind exact original value/row/period/unit/basis/scope evidence. See [metric policy](PRODUCT_METRIC_POLICY.md) for common-stockholder attribution, Tesla crypto revisions, AMD continuing operations and changed segment presentation.

[Development cases](fixtures/product/development_cases.v1.json) were frozen before generated development answers: 48 questions, eight per slice (multi-document, temporal scope, calculations/units, clarification, conflicts/revisions, missing evidence). There are **25 numeric cases**, eight narrative cases and eight answerable cross-company cases. Numeric labels use reviewed original cards and separately prepared Decimal calculations. Narrative labels retain reviewed original candidate passages and topic requirements. Missing reviewed cards are distinguished from absent original sources. The separate 48-question holdout is not opened, captured or used for tuning by the development runner.

## Bounded narrative drafting

Original passage search remains a zero-model candidate search by default. Selecting **Draft a cited narrative** adds at most one generator call (60-second timeout, no retries, at most 1,600 output tokens); the planner, VLM and embedding paths are not invoked. Each task receives a share of the existing 6,000-token original-evidence budget. Three lexical anchors may include their immediate original neighbors on the same physical page; every block retains a separate immutable locator. No generated captions become evidence.

A draft must cover every required task, remain in its task/company, quote an exact unique original substring and contain no number absent from that quote. Incomplete required coverage withholds generation; incomplete claims refuse a complete answer. These bounds establish provenance, **not semantic correctness**. Claims remain `unreviewed_generated_claim`, coverage remains `binding_unverified`, and UI displays the review qualification. Saved history reopens without model calls; an explicit narrative rerun can make another paid call.

## Capture and cost policy

Use the [private local runtime](PRODUCT_LOCAL_RUNTIME.md). The runner validates all frozen artifact hashes and authorized source/version/build/raw-byte pins before any paid call. Without `--capture`, it validates labels only. Captures require a new directory and retain full result JSONL, execution IDs, saved-history equality, original citations, source/card/code hashes, latency and raw provider usage.

```bash
GENERATOR_MODEL=gpt-6-luna REASONING_EFFORT=none .venv/bin/python scripts/run_product_development.py \
  --pricing docs/benchmarks/20261003-product-regression/pricing.json \
  --output-dir docs/benchmarks/20261003-product-development/capture --capture
```

The configured generator estimate uses $0.10/M input and $0.50/M output tokens ([official model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)). Raw token/cache details remain in each receipt; configured estimates do not claim an invoice or apply unmeasured cache discounts. Unknown usage/pricing stays unknown. No paid semantic judge runs.

The development summary reports mechanical outcome, reviewed numeric-binding and arithmetic checks with denominators. Strict authentic accuracy and semantic citation support remain undefined until the required separate review/evaluation gates pass. A matching expected outcome or an exact quote alone does not count as strict semantic success.

## Historical control

[Historical 30-question capture](benchmarks/20261003-product-regression/capture/summary.json) uses the unchanged historical question/label set, a separate `historical-regression` owner and the three retained original Q4 2025 PDFs. It creates current corrected-provenance builds from cached embeddings: no new embedding API call. Legacy Chroma vectors lack the required evidence revision and are not relabeled as verified.

All 30 questions were captured with `gpt-6-luna`, reasoning `none`, current original parent-child/BM25 retrieval and no VLM. Raw usage: 155,374 input / 1,741 output tokens, 30 generation calls; configured estimate $0.0164079. Total latency p50 1.494s / p95 2.666s. Mechanical outcome match is 22/30; original-locator validity is 20/20 questions issuing citations. Strict semantic support, numeric correctness and strict accuracy remain undefined (reviewed denominator zero). This control differs from older model/vector configurations and cannot establish the predeclared paired historical non-regression or cost gates without matched review.
