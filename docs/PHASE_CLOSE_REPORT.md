# Phase close — October 2, 2026

The full 30-question retained parent-child + BM25 answer benchmark is complete. **Retain the configuration; it is not ready for broader financial-comparison use.** Issue 12's disposable Docker build/start/restart/restore/resource validation is complete. No cloud deployment was performed.

## Run contract and evidence

The unchanged golden questions and `labels.v1.json` were hash-checked against the three original PDFs. The existing `experiment` owner has 3 active sources, 88 parents and 556 children; retained Postgres vectors and raw objects were reused, with no ingestion/contextualization calls. Runtime: GPT-6 Luna, `text-embedding-3-small` (1536 dimensions, exact cosine), BM25, fetch 20 per branch, RRF k=60, 800/150 parent/child sizes with 80/20 overlap, current quick/deep **3/8 parents**, no filters, no reranking/context hints/vision captions.

This is the deployed-policy answer baseline, **not** the prior common 2,400-token retrieval experiment. It has different final evidence recall; do not treat the 0.750 prior screen as today's answer-context recall. All 30 requests were run sequentially through `PersistentRAGService.query`, with a fresh query embedding and live generation. The initial `minimal` reasoning effort failed with HTTP 400; its empty attempt is preserved. The completed capture uses supported `none`, explicit 60-second generation timeout, no generation retries and a 4,096-token completion cap. The manifest pins code/configuration/corpus/label/build identities, vectors/chunks and dependencies without the DSN or credentials. A runtime sidecar pins Postgres/pgvector/private dependency versions and verifies that retained chunks/vectors are unchanged after the run.

Answers were reviewed by Codex against the frozen labels, retrieved original evidence, and relevant original PDF pages. This is source-and-rubric review, **not independent human review or Ragas**; no paid judge was run. Closely related qualitative propositions are grouped, primary financial amounts are separate review units, and cited support uses the union of footnotes attached to each proposition. The immutable raw answers are separate from the hash-bound review overlay. Exact-quote recall can miss equivalent evidence: q09 correctly uses page-29 GAAP evidence although its golden span is on page 10.

## Answer quality

| Metric | Result | Denominator / definition |
|---|---:|---|
| Numeric accuracy | **90.0%** | 9/10 labeled factual values; normalized entity/period/scope/unit/tolerance |
| Outcome-label agreement | 73.3% | 22/30 exact structured outcome matches |
| Outcome correctness | **70.0%** | 21/30 correct label and no reviewed unsupported/refuted assertion |
| Rubric completeness and correctness | 66.7% | 20/30; includes q08's correct value despite wrong citation |
| Strict answer correctness | **63.3%** | 19/30; correct outcome, complete rubric, faithful claims and supporting citations |
| OOC refusal correctness | **100%** | 4/4; deterministic fact-free refusals, zero assertions/citations |
| Clarification correctness | **0%** | 0/3: q18, q23, q24 all refuse |
| Unnecessary refusals | 7 | q07, q15, q16, q18, q21, q23, q24; 7/26 in-corpus questions |
| Citation validity | **100%** | 31/31 cited cards match original retrieved document/version/chunk/spans; zero invalid footnotes |
| Citation support, proposition weighted | **95.6%** | 43/45 reviewed factual propositions supported by their issued footnotes |
| Citation support, answer macro mean | 92.1% | 19 answering questions; q08 = 0, q22 = 0.5 |
| Faithfulness, proposition weighted | **97.8%** | 44/45 propositions supported by original retrieved context |
| Faithfulness, answer macro mean | 97.4% | 19 answers with factual propositions; 18/19 entirely faithful |
| Unsupported/wrong-period suggestions | 1 | q22's conflicting Q4 2024 54% suggestion, even though it subsequently retracts the trend |

Refusals have no factual-proposition or citation-support denominator; their safety is reviewed separately. The outcome-correctness metric does not require full rubric coverage or issued-citation support; use strict correctness for the phase decision. q08 has the correct $34,639M value (context 3's FY segment amounts also sum exactly to it), but cites a title/caution-only card. q22 tentatively says 54% to 54% "increased", then claims the trend is unavailable; the actual PDF page 10 reports **51% → 54%, +3 percentage points**. q14 explicitly dates April events correctly but mixes post-quarter highlights into a Q1 operations answer and omits core production/delivery/storage coverage; it is partial, not counted as a proved wrong-period factual assertion.

| Category | Strict correct | Outcome agreement | Final macro evidence recall | Complete golden evidence |
|---|---:|---:|---:|---:|
| Factual | 8/10 | 9/10 | 0.700 | 7/10 |
| Semantic | 4/8 | 4/8 | 0.750 | 6/8 |
| Single-document multi-hop | 2/4 | 3/4 | 0.667 | 2/4 |
| Cross-document | **1/4** | 2/4 | **0.458** | **1/4** |
| Out of corpus | 4/4 | 4/4 | Undefined | Undefined |
| All | 19/30 | 22/30 | 0.673 (26 questions) | 16/26 |

Semantic review: q11/q12/q13/q17 pass; q14 is partial; q15/q16 unnecessarily refuse; q18 misses clarification. Cross-document review: q23 misses revenue-period/definition clarification; q24 misses margin-basis/scope/period clarification; q25 correctly qualifies incomparable AI metrics but omits AMD Data Center +39%/Instinct growth evidence; q26 correctly compares both companies' risk statements. Only q26 is a complete cross-document success. Candidate recall@20 is 0.571 over 26 supported questions. These are 30 screening questions, with only four cross-document cases; no statistical significance or general-production accuracy claim is made.

## Latency, provider tokens and measured cost

| Quantity | Completed 30-question capture |
|---|---:|
| End-to-end service latency, mean / p50 / p95 | **2.278 / 1.956 / 3.261 s** |
| Maximum service latency | 8.723 s |
| Retrieval latency, mean / p50 / p95 | 0.385 / 0.362 / 0.691 s |
| Sum of per-question wall times | 69.833 s |
| Generator calls / query-embedding calls | 30 / 30 |
| Generator input / total completion tokens | **147,745 / 1,783** |
| Fresh query-embedding input tokens | 439 |
| Total input tokens / reported reasoning tokens | **148,184 / 0** |
| Reported cache reads / cache writes | 0 / 147,655 input tokens |
| Offline judge calls / ingestion calls | 0 / 0 |
| Measured benchmark model cost | **$0.019366155** |
| Mean measured query cost | **$0.000645539** |

Percentiles use linear interpolation across 30 queries. Service latency includes retrieval/generation; per-question wall timing also includes adapter setup. There is no online verification/judge latency. Reasoning is included in completion totals and not added again.

Dollar amounts use actual provider usage receipts multiplied by the standard tariffs verified October 2: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) input $0.10, cache reads $0.01, cache writes $0.125 and output $0.50 per million; [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small) input $0.02 per million. Every request is below the long-context threshold. Ordinary input excludes reported reads/writes; writes replace ordinary input charging. Generator cost is $0.019357375 and embedding cost $0.000008780. The coarse `CostTracker` snapshot prices all prompt tokens as normal input and reports $0.015674780 in raw summaries; **the receipt-based repricing sidecar is authoritative for this report**. The application default price table was not silently changed.

The Docker checks separately recorded 4 live queries plus 2 small Markdown builds: **$0.000223590** in model usage. Successfully receipted benchmark + Docker calls total **$0.019589745**. These are measured token-based charges, not account invoice reconciliation. The failed initial attempt has no complete usage receipt and is excluded from those totals; no account-wide or historical/context-cache costs are attributed to this run.

## Issue 12 — closed local validation

`Dockerfile.private` built and started as **Linux/arm64**, using an unprivileged UID 10001 API process. The image is 153,211,736 bytes (146.11 MiB). Chroma, Streamlit, Ragas, pytest and Jupyter are absent. Postgres/pgvector runs in an isolated network with a disposable persistent volume, **no published DB port**, 12 maximum connections, and 1 CPU / 512 MiB caps. The API is bound only to localhost, with bearer credentials in a temporary ignored file, tracing/access logs off, 1 CPU / 512 MiB caps and one process.

The retained SQL dump was restored into the Linux database. Three raw PDF object hashes match, owner isolation returns 404 for another owner's source, and missing auth returns 401. A documented `sources.py migrate` after restoring the older schema was required before registration writes. A Markdown byte upload was queued, processed by the image's bounded worker, activated and queried with resolved original evidence; a second version also activated without rebuilding the image. This proves updates work beyond read-only startup.

The first two-request test returned 503/503. Uvicorn rejects at `>= limit`, so the old limit `2` did not admit two simultaneous requests. The corrected threshold `3` yields **200/200**, with supported answers and isolated usage; the Dockerfile explains the threshold. Concurrent request wall times were 3.690 and 3.575 seconds.

| Resource / lifecycle check | Measured result |
|---|---:|
| API idle / two-query high-water memory | 117.18 / **205.16 MiB** |
| DB measured high-water memory | **114.40 MiB** |
| Small ingestion-worker high-water memory | **232.94 MiB** |
| Sum of separate observed process peaks | 552.50 MiB |
| API restart to authenticated ready | **2.148 s** |
| DB restart to authenticated ready | **0.493 s** |
| Fresh API container recreation to ready | **1.619 s** |
| Query after fresh container recreation | Supported answer/citation; 3.356 s wall |
| OOM / worker nonzero exit | None / none |

The existing 2 GB Lightsail proposal remains a reasonable **capacity candidate** for this small corpus: [documented idle estimate](PRIVATE_DEPLOYMENT.md) $13.50/month ($12 VM + $1 object bundle + 10 GB snapshots). Separate observed peaks are not a simultaneous measured sum. Worker measurement uses a tiny Markdown source, not the 100-page/3,000-child maximum; Linux/amd64, real S3 permissions, VM OS overhead and sustained-load behavior remain deployment checks. No cloud runtime, scheduler or public ingress was provisioned. Task-created containers/network/volume and temporary credentials are removed after validation; the retained original corpus/database remain intact.

## Recommended next phase: evidence-complete financial answers

1. **Clarification and scope correctness first.** Make q18/q23/q24 ask the required automotive/consolidated, GAAP/non-GAAP, period and revenue-definition questions. Clarification should not depend on finding enough context for a numeric answer. Preserve all four clean OOC refusals and the deterministic refusal formatter.
2. **Bounded evidence coverage and routing.** Recover the separate Gaming value (q07), Instinct ramp (q15), AI outlook (q16), all segment growth operands (q21), historical gross-margin operands (q22), and AMD growth in q25. Test broader routing for q16 and a small per-requested-source retrieval/coverage step for q23–q25; compare one variable at a time against this frozen baseline. Do not spend on another contextualization/embedding/reranking arm before testing these concrete gaps.
3. **Validate citations and financial arithmetic before synthesis.** Bind q08's number to its supporting source rather than the first/title card. Derive changes with `Decimal`/integers from period/scope/unit-bound operands; stop contradictory q22 output. Separate post-quarter operations from Q1 results in q14. Keep faithful partial answers distinct from complete answers.

Suggested exit criteria for this failure-focused phase: all 3 clarification cases correct, 4/4 OOC refusals retained, no unsupported/wrong-period assertions, every factual numeric answer cited to supporting evidence, and complete/source-balanced evidence for the comparison questions. Rerun the same 30 questions as paired review before expanding a frozen labeled set for fiscal-calendar conflicts, segment/consolidated scope and missing quarters. Preserve the existing promotion gates; this recommendation does not promote a new retrieval arm or authorize cloud provisioning.

## Reproduction and artifacts

```sh
# Existing migrated golden corpus; DATABASE_URL supplied privately. No rebuild.
REASONING_EFFORT=none python scripts/run_benchmark.py --backend postgres \
  --owner experiment --limit 0 --pricing docs/benchmarks/20261002-parent-bm25/pricing.json \
  --output-dir /tmp/finrag-new-answer-run
# Offline raw metrics; offline reviewed metrics and full tariff repricing.
python scripts/run_benchmark.py --replay docs/benchmarks/20261002-parent-bm25/results.jsonl
python scripts/replay_answer_review.py docs/benchmarks/20261002-parent-bm25
python -m pytest tests/unit/test_answer_review.py tests/unit/test_benchmark.py tests/unit/test_private_runtime.py -q
```

Artifacts: [manifest](benchmarks/20261002-parent-bm25/manifest.json), [immutable answers/contexts/usage](benchmarks/20261002-parent-bm25/results.jsonl), [raw summary](benchmarks/20261002-parent-bm25/summary.json), [source-review overlay](benchmarks/20261002-parent-bm25/review.json), [reviewed summary](benchmarks/20261002-parent-bm25/reviewed_summary.json), [full measured-cost sidecar](benchmarks/20261002-parent-bm25/measured_cost.json), [Docker receipts/resources](DOCKER_CHECK.json). Ten focused offline checks passed, including raw/review replay, hashes, numeric/citation counterexamples, full cache-write repricing and private dependency isolation. Original golden questions/labels and production retrieval defaults remain unchanged.

## Per-question disposition

| ID | Category | Expected outcome | Actual outcome | Strict review | Evidence / failure |
|---|---|---|---|---|---|
| q01 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q02 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q03 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q04 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q05 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q06 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q07 | fact_finding | answer | refuse | Fail | Unnecessary refusal: separate Gaming revenue exists in PDF page 22 (not combined Client and Gaming). Retrieved context lacks it. |
| q08 | fact_finding | answer | answer | Fail | Value agrees with golden label. Citation 1 contains title/caution only; original context 3 has $34,639 in an unlabeled reconstructed row and FY segment revenues sum to $34,639M. Faithful via exact operand sum, but issued citation does not support the claim. |
| q09 | fact_finding | answer | answer | Pass | Correct original evidence on page 29; exact golden page-10 recall misses an equivalent original-source occurrence. Do not revise labels after seeing results. |
| q10 | fact_finding | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q11 | semantic | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q12 | semantic | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q13 | semantic | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q14 | semantic | answer | qualified_answer | Partial | Grounded highlights, with April explicitly stated. Partial relevance to Q1 operations; production/deliveries/storage omitted and post-quarter events not separated. Qualified outcome differs from answer label; no proven wrong-period numeric assertion. |
| q15 | semantic | qualified_answer | refuse | Fail | Required Instinct continued-ramp passage page 21 is absent from final contexts; generic refusal instead of qualified answer. |
| q16 | semantic | qualified_answer | refuse | Fail | Market-outlook evidence page 5 is missing; factual router uses only 3 parents; generic refusal instead of qualified outlook. |
| q17 | semantic | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q18 | semantic | clarify | refuse | Fail | Refuses rather than asking automotive/consolidated scope clarification, despite consolidated margin context. |
| q19 | single_doc_multihop | answer | answer | Pass | Matches labeled outcome/reference; original cited evidence supports the answer. |
| q20 | single_doc_multihop | qualified_answer | qualified_answer | Pass | Operands and difference verified with integer arithmetic; causal/inventory trend uncertainty preserved. |
| q21 | single_doc_multihop | answer | refuse | Fail | Cannot rank all segments: Data Center growth passage absent; refusal instead of evidence-complete ranking (39%, 37%, 3%). |
| q22 | single_doc_multihop | answer | answer | Fail | Conflicting opening suggests 54% for Q4 2024 and an increase from 54% to 54%, then retracts. Original PDF page 10 is 51% to 54% (+3 percentage points); final contexts lack that table. |
| q23 | cross_doc | clarify | refuse | Fail | Generic refusal; no requested period/revenue-definition clarification. Only Wells Fargo label evidence is retrieved. |
| q24 | cross_doc | clarify | refuse | Fail | Generic refusal; no GAAP/non-GAAP/consolidated/automotive and period clarification. Both pinned comparison spans missing. |
| q25 | cross_doc | qualified_answer | qualified_answer | Partial | Correct qualification of incomparable standalone AI metrics, but misses AMD Data Center +39% and Instinct ramp. Partial golden-rubric coverage. |
| q26 | cross_doc | answer | answer | Pass | Both source risk lists and Tesla forward-looking caveat supported in their respective original excerpts. |
| q27 | out_of_corpus | refuse | refuse | Pass | Fact-free deterministic refusal; zero financial/world claims, judged against the expected outcome. |
| q28 | out_of_corpus | refuse | refuse | Pass | Fact-free deterministic refusal; zero financial/world claims, judged against the expected outcome. |
| q29 | out_of_corpus | refuse | refuse | Pass | Fact-free deterministic refusal; zero financial/world claims, judged against the expected outcome. |
| q30 | out_of_corpus | refuse | refuse | Pass | Fact-free deterministic refusal; zero financial/world claims, judged against the expected outcome. |
