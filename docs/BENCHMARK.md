# Reproducible benchmark

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
```

Each new directory contains `manifest.json`, append-flushed `results.jsonl` and `summary.json`. Completed rows survive a later error; existing directories are never overwritten. The manifest pins corpus/golden/label/code/configuration hashes, revision, index artifacts, model names and retrieval settings. Results retain the full question/label, candidates, final contexts, answer citations, outcome and usage when supplied by the query adapter. No paid run is part of CI.

Evidence recall counts each required span once, requires the original source hash and page plus the normalized original quote, and treats legacy/unresolved provenance as a miss. Recall@20, final recall, complete evidence and MRR use supported-question denominators. Quote-level matching is deliberately conservative: extractor formatting differences can cause misses and require reviewed span mappings, never relaxed source identity. Numeric accuracy requires reviewed `numeric_claims` with matching entity, period, scope and normalized unit; missing review is undefined, not a fabricated success. Arbitrary prose numbers do not demonstrate correctness. Semantic answers require rubric review. Ragas metrics, when supplied, are secondary; answer relevancy/context precision/recall are undefined for refusal/clarification cases. Every mean reports its denominator; empty denominators are null.

The capture default replays the deployed quick/deep 3/8-parent policy. It is **not** the planned common 2,400-token experiment budget. Arms A–D and that budget are Issue 10; use the same evidence/provenance corrections for all new arms, and record any legacy artifact as historical only. A harness smoke test does not establish retrieval quality.

## Promotion gate

Before promoting contextual retrieval: +0.10 absolute macro evidence recall within the same 2,400-token original-evidence budget; two additional correct factual numeric answers, with no formerly correct answer lost; no new wrong-period/scope assertions; all four out-of-corpus questions handled correctly; no invalid citations; mean faithfulness regression ≤0.02; online p95 latency and mean query cost increase ≤20%. Preapprove an ingestion/context budget. Report paired question deltas and uncertainty. Undefined numeric/citation review or unknown costs cannot pass the gate. Retain parent-child when results are inconclusive. Thirty questions are a screening set, not statistical proof.
