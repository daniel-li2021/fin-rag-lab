# Retrieval decisions

October 2, 2026 screening: retain parent-child plus BM25. All 30 unchanged golden questions were used; evidence recall has a 26-question denominator. Numeric/outcome/faithfulness/citation review is a separate gate, not inferred from retrieval.

| Arm | Child recall@20 | Final recall at 2400 tokens | Delta vs A |
|---|---:|---:|---:|
| A: parent-child reference | 0.571 | 0.750 | +0.000 |
| B: deterministic metadata + parents | 0.718 | 0.724 | -0.026 |
| C: Luna context + parents | 0.641 | 0.699 | -0.051 |
| D: Luna context, original children | 0.641 | 0.641 | -0.109 |

The deterministic prefix improves child ranking but loses evidence after parent expansion under the common budget. Neither prefix arm passes the +0.10 final-recall gate, and removing parents loses more evidence. Additional paid generation/judging, alternate embeddings and reranking were therefore not run for these losing configurations. No production retrieval default changed.

The controlled corpus contains the three hash-pinned public PDFs and 556 corrected children, with unchanged 800/150 parent/child sizes and original evidence across arms. Vision captions were disabled consistently, so this is a fresh original-evidence reference, not a claim that the legacy unprovenanced Chroma artifact was imported. Context batches used GPT-6 Luna, with exact supporting-quote validation, a 100-token prefix ceiling and abstention on missing/unsupported prefixes. 26 prefixes abstained. Context-document ordering is pinned in the manifest as page-string/block-ID order; it differs from natural document order and is a limitation of this screen. A later experiment should use natural ordinal order as a separately manifested change.

The 12 cached context batches record 275201 input and 73107 total completion tokens. Luna prices are unverified in the repository, so dollar cost remains unknown. Resumed batches and all corpus embeddings reused saved outputs; cached usage is included separately from fresh-run counters. Interrupted attempts can have unrecorded usage, so this is not a billing reconciliation or a reliable original wall-time total. The final results/manifest are in `CONTEXTUAL_CHECK.json`; full per-question original contexts and candidates remain under the ignored `index/experiment-20261002/` run directory. Paired deltas are screening evidence, not a statistical significance claim.

## Persistent and lexical parity

Exact Postgres cosine search plus BM25 produced the same fused child ranking as the trusted local cosine/BM25 reference on **30/30 questions**. Both used the same cached embedding inputs/vectors, source universe, fetch limit 20, RRF k=60 and 2400-token evidence budget. This proves this snapshot's ranking parity; it does not assign an embedding model to the older Chroma collection. The explicit three-PDF migration rejected that collection's unverifiable model/evidence provenance, rebuilt from raw objects and valid caches, and incurred **zero new model calls**.

PostgreSQL `simple`/GIN/`ts_rank_cd` lexical ranking was tested as a separate branch against BM25 with the same vector branch and filters. SQL ranking had final macro recall **0.686**, versus **0.750** for BM25; keep BM25. Local end-to-end retrieval/budget p50/p95 were approximately 1191/1757 ms for BM25 and 1075/2083 ms for SQL, over 30 queries. These include SQL decode and token-budget selection on this workstation, not a deployed latency SLA. Per-question ranking changes and exact values are in `LEXICAL_CHECK.json`. Identifier coverage and source-authorization behavior are also exercised by the focused database checks; no search-cluster dependency was added.

## Metadata and live checks

Six synthetic metadata cases yielded **23/24 exact field matches**. Eight fields abstained, including the genuinely missing company/period fields and one conservative document-type miss. Supporting quotes were validated, repeat calls hit the cache, and suggestions never changed confirmed metadata. This does not establish accuracy on ambiguous, amended or multi-period real filings; confirmation remains required. Results/usage/limitations are in `METADATA_CHECK.json`.

A bounded Luna smoke check answered Wells Fargo's Q4 2025 net income with a resolved original-source citation and recognized all four out-of-corpus questions as refusals. The model sometimes inserted other-company/other-period facts into refusal prose despite prompt instructions. The shared generator now renders a deterministic, fact-free refusal for `outcome=refuse`; existing API replies were replayed through that guard without another paid call. The offline check deliberately supplies a refusal containing a bogus number/citation and verifies both are removed. `LIVE_CHECK.json` retains the original replies and marks the formatter replay; it is five smoke questions, not a full judged answer benchmark.

Validation includes focused unit checks, real disposable Postgres/pgvector owner/archive/lease/failure checks, authenticated byte uploads, immutable object hashes and SQL backup restoration. Private runtime limitations and the deployment-time Docker check are documented in [the deployment profile](PRIVATE_DEPLOYMENT.md).

## Follow-up metric validation and remaining gates

All four saved screens were replayed without model calls; their published summaries match exactly. A portable, label-bound scoring fixture now permits that check in a fresh checkout. Lexical paired deltas/percentiles, 30/30 vector ranking parity, metadata totals and the 12 cached context usage events have offline regression checks. Citation scoring now rejects citations that merely claim resolution but do not match retrieved original evidence. Missing verification and reasoning usage remain undefined.

Reference A's category results separate evidence availability from answer accuracy:

| Category | Final macro evidence recall | Complete evidence | Questions |
|---|---:|---:|---:|
| Factual | 0.900 | 9/10 | 10 |
| Semantic | 0.750 | 6/8 | 8 |
| Single-document multi-hop | 0.667 | 2/4 | 4 |
| Cross-document | 0.458 | 1/4 | 4 |
| All supported | 0.750 | 18/26 | 26 |

Next quality work should target AMD's missing gross-margin evidence (q09/q22), AMD outlook/segment coverage (q16/q21), and cross-document completeness (q23–q25), while treating q23/q24 as clarification cases. q15 already has candidate evidence but loses it within the final budget; test budget allocation before spending on new contextualization. Preserve the current baseline and change one variable per experiment. These are retrieval misses, not measured wrong answers.

Deployment readiness is not established: full numeric/semantic/citation/faithfulness review is still absent, model dollar cost is unknown, and Docker build/start plus resource sizing remain unchecked. The private factory now passes a subprocess check with Chroma, Streamlit and evaluation/notebook packages unavailable, and no legacy app/index is initialized by importing it. This closes a concrete import-isolation gap but does not replace Linux image validation or justify provisioning.
