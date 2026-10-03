# Fin-RAG-Lab

A financial research prototype built around real Wells Fargo, Tesla and AMD reports, with cited Ask answers and an opt-in workspace for reviewed facts, calculations and saved research. Seven notebooks explain the underlying parsing, retrieval, generation and evaluation. Authentic multi-document release evaluation remains held; see the [current product review and next batch](docs/PRODUCT_NEXT_BATCH_PLAN.md).

[![CI](https://github.com/daniel-li2021/fin-rag-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/daniel-li2021/fin-rag-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

---

## Historical notebook result

These retained notebook results describe an earlier experiment, not current Ask accuracy or Phase 3 multi-document validation. Current evidence and remaining release gates are summarized in the [product review](docs/PRODUCT_NEXT_BATCH_PLAN.md).

Switching from a naive `RecursiveChunker(400/60)` to a `ParentChildChunker(parent=800, child=150)` with parent-expansion at retrieval time, evaluated on a 30-question financial QA set with Ragas:

| Metric | Baseline | Improved | Δ |
|---|---:|---:|---:|
| faithfulness | 0.765 | **0.881** | +0.116 |
| answer_relevancy | 0.386 | **0.618** | +0.232 |
| context_precision | 0.447 | **0.793** | +0.346 |
| context_recall | 0.467 | **0.667** | +0.200 |
| likely-hallucination cases (faith<0.5) | 3 / 30 | **0 / 30** | — |

By category (faithfulness):

| Category | n | Baseline | Improved | Δ |
|---|---:|---:|---:|---:|
| fact_finding | 10 | 0.735 | **0.960** | +0.225 |
| out_of_corpus | 4 | 0.484 | **0.720** | +0.236 |
| single_doc_multihop | 4 | 0.792 | 0.835 | +0.043 |
| semantic | 8 | 0.908 | 0.923 | +0.015 |
| cross_doc | 4 | 0.810 | 0.810 | 0.000 |

**Worked example — Q0**, "What was Wells Fargo's Q4 2025 net income?" (ground truth $5.4B):
- **Baseline** retrieved the right page but couldn't pin the number — produced a hedged "I found several candidate figures" answer (faith=0.60).
- **Improved** answered "$5,361 million ($5.4 billion)" directly (faith=1.00).

The full reproduction is `notebooks/05_evaluation.ipynb`. Numbers above came from a real run and are saved as `tmp_baseline_ragas.csv` / `tmp_improved_ragas.csv` (gitignored).

The `cross_doc` flat line is the next thing to chase — parent-child helps within a document, not across.

---

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Keys
cp .env.example .env
# edit .env: OPENAI_API_KEY=sk-...   (LANGSMITH_* optional, only needed for notebook 06)

# 3. PDFs — download into data/uploads/  (URLs in Footnotes below)
#    wells_fargo.pdf, tesla.pdf, amd.pdf

# 4. Warm the cache (once, ~3.5 min, ~$0.025)
python scripts/precompute_cache.py \
    --inputs data/uploads/wells_fargo.pdf \
             data/uploads/tesla.pdf \
             data/uploads/amd.pdf

# 5. Open the first notebook
jupyter lab notebooks/00_quickstart.ipynb
```

If you have a pre-built `cache_bundle.zip`, unzip it at the repo root instead of step 4 — the cache is content-addressed, so a teammate's bundle works on your machine bit-for-bit.

---

## Application (local)

Phase 3 includes opt-in immutable reviewed facts, pinned numeric research, cited Decimal receipts, bounded original-passage search, named collections and saved history with separate reruns. Select **Research** in the persistent Streamlit app or use the private research API. See [implementation and usage](docs/PHASE_3_IMPLEMENTATION.md) and the [frozen evaluation contract](docs/PHASE_3_EVALUATION.md). Authentic binding gaps and holdout evaluation keep release promotion held.

The notebooks remain the teaching path. For a runnable app, a thin service layer wraps the same `src/` modules using the **parent-child** strategy from notebook 05 (not the recursive baseline).

```bash
# Build / load the index (parent=800, child=150, hybrid RRF + parent expansion)
python scripts/build_index.py

# Ask a question from the CLI
python scripts/query_cli.py "What was Wells Fargo's Q4 2025 net income?"
python scripts/query_cli.py --verify "What was Tesla's vehicle production?"   # optional hallucination check
python scripts/query_cli.py --interactive

# Offline Ragas evaluation (separate from online queries)
python scripts/run_eval.py --limit 5
python scripts/run_eval.py --limit 0 --output tmp_app_ragas.csv   # full golden set

# Streamlit UI
streamlit run app/streamlit_app.py
# open http://localhost:8501
```

| Piece | Role |
|---|---|
| `src/services/rag_service.py` | Shared ingest / index / query / evaluate orchestration |
| `scripts/build_index.py` | Build or rebuild the local `index/` |
| `scripts/query_cli.py` | Online queries from the terminal |
| `scripts/run_eval.py` | Offline Ragas pipeline |
| `app/streamlit_app.py` | Upload/select PDFs, ask questions, show citations + latency/cost/trace |
| `src/api/server.py` | FastAPI adapter over the same `RAGService` |

Ragas stays offline (`run_eval.py`). The Streamlit UI may optionally run `HallucinationDetector` on a single answer; it does not run the full Ragas suite.

For persistent source updates, install `requirements-persistence.txt`, configure `DATABASE_URL` and private objects, then run `python scripts/sources.py migrate`. The [durable-source guide](docs/PERSISTENCE.md) covers registration, text/Markdown, bookmarks/snapshots, metadata confirmation, migration and the authenticated API. With `DATABASE_URL`, Streamlit uses that registry instead of rebuilding a shared PDF corpus. Parent-child plus BM25 remains the default after the [controlled comparisons](docs/RETRIEVAL_RESULTS.md).

### Docker (local)

The [full 30-question phase-close report](docs/PHASE_CLOSE_REPORT.md) records numeric accuracy **9/10**, strict answer correctness **19/30**, OOC refusals **4/4**, clarification **0/3**, and measured model cost **$0.019366155**. Issue 12's disposable Linux Docker build/start/restart/restore/resource checks pass. Subsequent [financial evidence experiments](docs/NEXT_PHASE_PLAN.md) remain held after correctness regressions; the final ordinary path has only a selected 12-question follow-up. [Phase 3 implementation](docs/PHASE_3_IMPLEMENTATION.md) now includes reviewed observation contracts, pinned research, calculations and saved history; authentic bindings and sealed evaluation remain incomplete, and the optional planner is disabled. The [next product batch proposal](docs/PRODUCT_NEXT_BATCH_PLAN.md) prioritizes real report histories, evaluation and Streamlit demonstration.

`.env` is **not** baked into the image. Pass it at runtime. Mount volumes so uploads/index/cache persist on the host.

```bash
docker build -t fin-rag-lab .

docker run --rm --env-file .env -p 8501:8501 \
  -v "$(pwd)/data/uploads:/app/data/uploads" \
  -v "$(pwd)/index:/app/index" \
  -v "$(pwd)/cache:/app/cache" \
  fin-rag-lab
```

Then open http://localhost:8501. Ingest PDFs in the UI (or pre-build with `python scripts/build_index.py` on the host so `index/` is ready before `docker run`).

---

## Lab progression

| # | Notebook | Topic |
|---|---|---|
| 00 | `quickstart` | 30 lines of LangChain LCEL — feel the chain before abstracting it |
| 01 | `parsing` | Multi-stage ingestion: PyMuPDF loader → struct parser → VLM captioner, with content-addressed caching |
| 02 | `chunking` | Three chunking strategies (fixed-size, recursive, parent-child) compared via a `CoverageDiagnostic` tool |
| 03 | `retrieval` | Vector + BM25 + RRF hybrid, with parent-child swap at retrieval time |
| 04 | `generation` | LangGraph state machine: short-query bypass, retrieve-generate, refusal-on-empty |
| 05 | `evaluation` | Ragas 4-metric eval + custom claim-level `HallucinationDetector` for compliance |
| 06 | `observability` | `@traceable` instrumentation + LangSmith dashboard + FastAPI `/ingest` and `/query` endpoints |

---

## Architecture

The [next-phase plan](docs/NEXT_PHASE_PLAN.md) now includes an opt-in durable source registry and Postgres/private-object backend. See [source lifecycle, API/UI and migration](docs/PERSISTENCE.md), [controlled retrieval results](docs/RETRIEVAL_RESULTS.md), and [prepared private deployment](docs/PRIVATE_DEPLOYMENT.md). Without `DATABASE_URL`, the notebook/local Chroma architecture below remains the default.

```
                    [ User uploads PDF ]
                            ↓
┌──────────────────────────────────────────────┐
│  IngestionPipeline                           │
│   Loader → Parser → Captioner (VLM)          │
│   3-layer content-addressed cache            │
└──────────────────────────────────────────────┘
                            ↓
                       Document
                            ↓
                       Chunker (Strategy: 3 implementations)
                            ↓
                  Vector + BM25 indexes
                            ↓
                    HybridRetriever (RRF)  ← optional parent expansion
                            ↓
              QueryPipeline (LangGraph state machine)
                            ↓
                     Answer + citations
                            ↓
            Ragas + HallucinationDetector → metrics
                            ↓
                   LangSmith → dashboard
```

---

## Repo structure

```
fin-rag-lab/
├── README.md
├── LICENSE
├── requirements.txt
├── .env.example
├── app/
│   └── streamlit_app.py        # local Streamlit MVP
├── scripts/
│   ├── build_index.py          # build parent-child hybrid index
│   ├── query_cli.py            # online CLI queries
│   ├── run_eval.py             # offline Ragas evaluation
│   ├── precompute_cache.py     # one-shot, generates shareable cache_bundle
│   └── build_notebooks.py      # rebuilds .ipynb from src
├── src/
│   ├── core/                   # domain models, abstract interfaces, cache, config
│   ├── loaders/                # Stage 1: PDF → page dicts
│   ├── parsers/                # Stage 2: structured Block detection
│   ├── captioners/             # Stage 3: VLM table/image captioning
│   ├── chunkers/               # 3 strategies, all `Runnable`
│   ├── retrievers/             # Vector / BM25 / Hybrid (RRF)
│   ├── generators/             # Citation-aware RAG generator
│   ├── evaluators/             # Ragas + claim-level hallucination + coverage
│   ├── pipelines/
│   │   ├── ingestion.py        # IngestionPipeline orchestrator
│   │   └── query.py            # LangGraph state machine
│   ├── services/               # app orchestration (RAGService)
│   ├── observability/          # CostTracker, LangSmith helpers
│   └── api/                    # FastAPI demo (POST /ingest, /query)
├── notebooks/                  # 00–06, see Lab progression above
├── data/
│   ├── uploads/                # PDFs go here
│   └── golden_set/             # 30 financial QA across 5 categories
├── cache/                      # auto-managed, content-addressed
├── index/                      # local app index (gitignored)
└── tests/                      # unit + integration tests
```

---

## Design choices

### Strategy pattern + dependency injection everywhere
Every stage has a `BaseX` abstract class; concrete implementations inherit and override. You can swap PyMuPDF for LlamaParse, or OpenAI embeddings for Cohere, without touching the pipeline.

### Chunkers inherit from `Runnable`
First-class LangChain ecosystem citizens — you can do `chunker | embedder | indexer`, or `.batch()` / `.stream()`. But chunkers also keep their own semantic methods (`chunk()`, `chunk_with_parents()`) so the architecture isn't married to LangChain's evolving API.

### Content-addressed caching
Cache keys are SHA256 of inputs. Three guarantees:
1. **Correctness** — change input, change key. No stale data, ever.
2. **Sharable** — zip the cache, ship to a teammate, instant warm-up on their machine.
3. **Reproducible** — same inputs → same key on every machine, every time.

### VLM captioning eagerly at ingestion (not lazily at query)
Read-side latency is the customer-facing metric. We pay the VLM cost once at ingest (cached forever) so query latency stays p99 < 1s. Lazy VLM at query time would put a 2–3 second LLM call on the hot path.

### LangGraph for query (not just an LCEL chain)
Production RAG isn't linear:
- Short factual queries → top-3 chunks suffice (save cost)
- Long analytical queries → top-8 with parent expansion (more context)
- Empty retrieval → don't call the LLM (refuse → save $ + prevent hallucination)

That's a state machine with conditional edges. Every node is `@traceable`, so each branch shows up independently in LangSmith.

### Custom `HallucinationDetector` on top of Ragas
Ragas faithfulness gives one score per answer. Compliance-critical domains (finance, legal) need to point at *which* claim is unsupported. The detector decomposes an answer into atomic claims and verifies each against the joined context with NLI-style prompts, returning per-claim verdicts. Actionable in a UI: highlight the unsupported sentence in red.

### `compare_strategies` instead of hard-coding "use parent-child"
The right chunking strategy depends on your query distribution. We ship a tool, not a recommendation. `CoverageDiagnostic` quantifies "did retrieval get the data we needed?" in 30 lines. `compare_strategies(chunkers, doc, queries, retriever_factory)` lets a team make a measurement-driven decision in 5 minutes on a new corpus.

---

## What we observed on the real PDFs

| Document | Pages | Text blocks | Tables | Images | Time | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Wells Fargo Q4 2025 | 12 | 418 | **0** | 1 | 6s | $0.0004 |
| Tesla Q1 2026 | 31 | 530 | 11 | 10 | 95s | $0.0061 |
| AMD Q4 2025 | 34 | 482 | 21 | 61 | 112s | $0.0187 |
| **Total** | 77 | 1,430 | 32 | 72 | ~3.5 min | **$0.025** |

Two teaching moments:

1. **Wells Fargo: 0 tables detected.** PyMuPDF's `find_tables()` cannot recover tables that are laid out as positioned text without an underlying table structure — common for press-release-style PDFs. The financial data *is* there, but fragmented across 418 text blocks. This is exactly the failure mode `02_chunking.ipynb` opens with: a generic `CoverageDiagnostic` tool reveals fixed-size chunking can't retrieve the table content even when asked direct questions. We don't hard-code "WF misses tables" anywhere — the tool measures it.

2. **AMD: 36 cache hits within itself** (out of 104 lookups). AMD's slide deck reuses the same logo / page-header / footer images across pages. Content-addressed caching deduplicates them automatically — proof the cache key design works without writing a test.

---

## What this lab is NOT

- Not a teach-LangChain-from-scratch course (we use LangChain components but reorganize them around our own abstractions).
- Not exhaustive coverage of every chunking strategy (we cover 3; semantic chunking and contextual retrieval are discussed conceptually in `02_chunking`).
- Not a deployment course (`06` shows a FastAPI demo; real cloud deployment is its own project).

---

## Footnotes

**Source PDFs** (download manually):
- Wells Fargo Q4 2025: https://www.wellsfargo.com/assets/pdf/about/investor-relations/earnings/fourth-quarter-2025-earnings.pdf
- Tesla Q1 2026 Update: https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q1-2026-Update.pdf
- AMD Q4 2025 Earnings Slides: https://d1io3yog0oux5.cloudfront.net/_b0eb9fe85e9ee1621001cc760a9e1d73/amd/db/841/9223/presentation/AMD+Q4'25+Earnings+Slides+FINAL.pdf

**License**: MIT — see [LICENSE](LICENSE).

## Benchmark, evidence and usage foundation

The original 30-question golden set is preserved with hash-pinned, corrected labels. New chunks preserve original table evidence and exact source spans; answer citations are separate from retrieved context. Queries report structured outcomes and isolated usage receipts, including verification and embedding calls. Unknown usage/pricing yields an unknown cost, and configured prices are estimates.

```sh
python scripts/run_benchmark.py --limit 5 --output-dir /tmp/finrag-benchmark
python scripts/run_benchmark.py --replay /tmp/finrag-benchmark/results.jsonl
python -m pytest -q
```

Capture uses an explicitly rebuilt evidence-revision-1 index; it does not rebuild or run judges automatically. Add `--verify` or `--ragas` only for a budgeted experiment. See [benchmark labels and promotion gates](docs/BENCHMARK.md), [evidence and migration contract](docs/EVIDENCE.md), and [usage/cost semantics](docs/USAGE.md). Historical notebook/CSV headline scores are not measurements of this corrected baseline.
