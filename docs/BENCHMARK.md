# Reproducible benchmark

The [October 2 full answer benchmark and phase close](PHASE_CLOSE_REPORT.md) now records all 30 questions on retained parent-child + BM25: numeric 9/10, strict answer correctness 19/30, OOC refusal 4/4, clarification 0/3, and complete cross-document answers 1/4. Its source-reviewed overlay is distinct from immutable model output; no Ragas or independent human judging is claimed. Provider token receipts, cache-write-aware measured pricing and Docker validation are included.

The historical `data/golden_set/golden.jsonl` stays unchanged. `labels.v1.json` pins its hash and the three original PDF hashes, assigns stable q01–q30 IDs, and supplies corrected references, expected outcomes, exact PDF page/text spans, numeric units/tolerances, entity, period and scope. Quotes are source evidence, not generated captions or transient chunk IDs. Labels must be reviewed/versioned before examining experiment results.

The original cross-document revenue ranking is incorrect: the reported amounts put Tesla above Wells Fargo, but use different quarters. q23 requires period/definition clarification; q24 requires margin basis/scope clarification. q18 must not substitute consolidated margin for automotive margin. AI progress is not automatically comparable AI revenue growth. Gaming revenue is distinct from combined Client and Gaming revenue. Missing historical factual values now have explicit numeric labels verified from the local PDFs.

## Capture and replay

```sh
# Bounded model work against an existing index; never rebuilds automatically.
python scripts/run_benchmark.py --limit 5 --output-dir /tmp/finrag-run-01
# All 30 questions, only when the model budget has been approved.
python scripts/run_benchmark.py --limit 0 --output-dir /tmp/finrag-run-02
# No model calls; recompute metrics/denominators from saved per-question results.
python scripts/run_benchmark.py --replay /tmp/finrag-run-01/results.jsonl
# The opt-in durable backend uses the existing, migrated, golden-only owner.
# DATABASE_URL is supplied privately; no index rebuild occurs.
REASONING_EFFORT=none python scripts/run_benchmark.py --backend postgres --owner experiment \
  --limit 0 --pricing docs/benchmarks/20261002-parent-bm25/pricing.json --output-dir /tmp/finrag-durable-run
# Replay the published review and full tariff calculation without paid work.
python scripts/replay_answer_review.py docs/benchmarks/20261002-parent-bm25
```

For the implemented financial evidence profile add `--supplement-k 8`; the default remains 0. `--ids q18 q23 q24` selects stable regression IDs; unknown IDs reject. `--reuse-query-embeddings` is a Postgres-only switch using the existing content/model/input-hash embedding cache, with fresh-call usage still recorded on a miss. Positive supplements also enable the experimental quote/calculation protocol. The [financial protocol results](PHASE_CLOSE_REPORT.md#subsequent-financial-evidence-implementation) failed quality promotion and preserve the frozen baseline; quote matching never replaces source/rubric review.

Each new directory contains `manifest.json`, append-flushed `results.jsonl` and `summary.json`. Completed rows survive a later error; existing directories are never overwritten. The manifest pins corpus/golden/label/code/configuration hashes, revision, index artifacts, model names and retrieval settings. Results retain the full question/label, candidates, final contexts, answer citations, outcome and usage when supplied by the query adapter. No paid run is part of CI.

Evidence recall counts each required span once, requires the original source hash and page plus the normalized original quote, and treats legacy/unresolved provenance as a miss. Recall@20, final recall, complete evidence and MRR use supported-question denominators. Quote-level matching is deliberately conservative: extractor formatting differences can cause misses and require reviewed span mappings, never relaxed source identity. Numeric accuracy requires reviewed `numeric_claims` with matching entity, period, scope and normalized unit; missing review is undefined, not a fabricated success. Arbitrary prose numbers do not demonstrate correctness. Citation validity requires the cited chunk/document/version and original spans to match a retrieved context; a `resolved` flag alone is insufficient. Citation support still requires claim review. Empty/incomplete verification cannot establish a correct refusal, and missing reasoning usage remains unknown. Semantic answers require rubric review. Ragas metrics, when supplied, are secondary; answer relevancy/context precision/recall are undefined for refusal/clarification cases. Every mean reports its denominator; empty denominators are null.

The capture default replays the deployed quick/deep 3/8-parent policy. It is **not** the common 2,400-token experiment budget. `scripts/compare_retrieval.py` now implements A–D using identical child boundaries/vector profiles, the same candidate/fusion settings, and one deduplicated original-evidence token budget. It reuses the durable corpus and caches, writes per-question results and a manifest, and shortlists by retrieval before paid answer judging. `scripts/compare_lexical.py` holds vectors/filters/fusion/budget fixed while comparing SQL lexical ranking separately. Recorded [retrieval results](RETRIEVAL_RESULTS.md) retain parent-child plus BM25. A harness smoke test does not establish retrieval quality.

## Promotion gate

Before promoting contextual retrieval: +0.10 absolute macro evidence recall within the same 2,400-token original-evidence budget; two additional correct factual numeric answers, with no formerly correct answer lost; no new wrong-period/scope assertions; all four out-of-corpus questions handled correctly; no invalid citations; mean faithfulness regression ≤0.02; online p95 latency and mean query cost increase ≤20%. Preapprove an ingestion/context budget. Report paired question deltas and uncertainty. Undefined numeric/citation review or unknown costs cannot pass the gate. Retain parent-child when results are inconclusive. Thirty questions are a screening set, not statistical proof.

Request usage, structured outcomes, verification, optional secondary judging and reporting semantics: [Usage contract](USAGE.md). Capture requires a corrected evidence revision; legacy artifacts remain available for historical inspection, not new promotion measurements.

The published A–D screen has a portable scoring fixture at `data/golden_set/retrieval_screen.v1.json`, bound to the label hash and raw result hashes. It keeps candidate IDs/ranks, matching original spans, measured retrieval latencies and cached context usage events. Unmatched context is omitted; this fixture recomputes scoring and summaries, not retrieval or token-budget selection. Full contexts stay in the ignored experiment directory. `python -m pytest tests/unit/test_benchmark.py tests/unit/test_screening_metrics.py` checks recall, MRR, completeness, paired deltas, latency percentiles, numeric tolerances/identity, citation resolution, review denominators, lexical aggregates/parity, metadata counts and unknown costs without model calls or a database.
