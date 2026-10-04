# Notebook and local compatibility usage

The seven notebooks remain the teaching path. [README](../../README.md) starts with the persistent research prototype; [STATE](../STATE.md) owns current results. These local commands use the compatibility index and may make paid embedding/model calls; reuse a valid existing cache/index and budget new work explicitly.

```sh
pip install -r requirements.txt
cp .env.example .env
# Set credentials privately; place the original PDFs in data/uploads/.
python scripts/precompute_cache.py --inputs data/uploads/wells_fargo.pdf data/uploads/tesla.pdf data/uploads/amd.pdf
jupyter lab notebooks/00_quickstart.ipynb
```

A prebuilt `cache_bundle.zip` can supply matching cached outputs. Configuration/code/input hashes decide cache reuse; a cache hit alone does not establish financial provenance.

| Notebook | Topic |
| --- | --- |
| [00 quickstart](../../notebooks/00_quickstart.ipynb) | Minimal LCEL chain |
| [01 parsing](../../notebooks/01_parsing.ipynb) | Loader, structured parser and cached VLM captioning |
| [02 chunking](../../notebooks/02_chunking.ipynb) | Fixed, recursive and parent-child coverage |
| [03 retrieval](../../notebooks/03_retrieval.ipynb) | Vector/BM25/RRF and parent expansion |
| [04 generation](../../notebooks/04_generation.ipynb) | Query graph, routing and empty-context refusal |
| [05 evaluation](../../notebooks/05_evaluation.ipynb) | Offline Ragas and claim checks |
| [06 observability](../../notebooks/06_observability_fastapi.ipynb) | Optional traces and legacy API demonstration |

```sh
python scripts/build_index.py
python scripts/query_cli.py "What was Wells Fargo's Q4 2025 net income?"
python scripts/query_cli.py --verify "What was Tesla's vehicle production?"
python -m streamlit run app/streamlit_app.py
```

These commands do not select persistent Research unless `DATABASE_URL` is configured. `scripts/run_eval.py` is an offline diagnostic; [BENCHMARK](../BENCHMARK.md) owns manifested experiments/replay. Notebook metrics below are historical measurements, not current Ask/research accuracy or evidence of a latency SLA.

## Historical notebook result

These retained notebook results describe an earlier experiment, not current Ask accuracy or Phase 3 multi-document validation. Current evidence and remaining release gates are summarized in the [current state](../STATE.md).

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

The unchanged `cross_doc` scores describe this historical experiment; they do not measure the implemented research workspace.


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


## Original teaching PDFs

- [Wells Fargo Q4 2025](https://www.wellsfargo.com/assets/pdf/about/investor-relations/earnings/fourth-quarter-2025-earnings.pdf)
- [Tesla Q1 2026 update](https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q1-2026-Update.pdf)
- [AMD Q4 2025 slides](https://d1io3yog0oux5.cloudfront.net/_b0eb9fe85e9ee1621001cc760a9e1d73/amd/db/841/9223/presentation/AMD+Q4%2725+Earnings+Slides+FINAL.pdf)

The corrected historical benchmark labels and raw hashes in [BENCHMARK](../BENCHMARK.md) are authoritative for experiments. These download URLs describe the teaching inputs, not an acquisition guarantee. Full original README wording remains in Git history.
