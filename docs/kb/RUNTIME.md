# Runtime and reproduction

The [README](../../README.md) has install/start commands. Reuse the private local cluster, originals and matching caches; a fresh checkout needs verified acquisition, reviewed windows, explicit ingestion and original fact bindings before reproducing the corpus. [STATE](../STATE.md) owns corpus/results; [System](SYSTEM.md) owns lifecycle/API semantics.

## Local Postgres and Streamlit

Start or reuse the installed `pgserver` development runtime:

```sh
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/local_postgres.py status
set -a
source index/product-local/runtime.env
set +a
GENERATOR_MODEL=gpt-6-luna REASONING_EFFORT=none .venv/bin/python -m streamlit run app/streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8502
```

The ignored profile contains the database connection and owner, never a copied API key. The app reads the existing ignored `.env` as a fallback; explicit exported settings take precedence. The local UI binds only to loopback. The cluster and objects live under ignored `index/product-local/`; the directory is private, the server listens only on a Unix socket, and `finrag_app` has no superuser, database-creation or role-creation privilege. `start` is repeatable and retains identities; process exit does not stop Postgres. `stop` performs a normal shutdown and retains the cluster. This is a local development runtime, without an automatic reboot launch agent or backup service.



The frozen inventory, official acquisition alternatives, raw hashes and reviewed physical windows are under [product fixtures](../fixtures/product/). `scripts/prepare_product_corpus.py --acquire` retains missing originals; `scripts/ingest_product_corpus.py` validates without model calls and `--ingest` submits explicit embeddings. Source registration/worker publication is atomic, cache-aware and last-good preserving. Candidate review packets are not verified financial facts. Named bindings use [financial policy](FINANCIAL_POLICY.md); no development command opens the release holdout.

## Private Docker profile

`Dockerfile.private` is a prepared API/worker profile, not a cloud deployment. It omits Chroma, Streamlit, notebooks and evaluation dependencies; corpus updates require no image rebuild. The preserved [Docker check](../evidence/checks/DOCKER_CHECK.json) covers an earlier small-corpus local Linux/arm64 run, not amd64, expanded-corpus sustained capacity or cloud permissions. Dated tariffs in receipt artifacts are not current hosting quotations; measure the full process set and verify pricing before deployment.

Use one small Linux Lightsail VM, one PostgreSQL/pgvector process on a persistent volume, and a private S3-compatible bucket. The application container is disposable; the database volume and bucket are not. This is a single-node private profile with an operator-managed database, not high availability. Keep PostgreSQL off public interfaces and the API reachable through an SSH tunnel/private authenticated proxy. Do not add an ALB, NAT gateway or public database for this tiny corpus. Configure private bucket access and scoped AWS credentials before an eventual deployment.

```sh
# Local validation is complete; cloud provisioning still requires its own request.
docker build -f Dockerfile.private -t finrag-private .
# Supply DATABASE_URL, FINRAG_BUCKET, AWS_DEFAULT_REGION, OPENAI_API_KEY,
# FINRAG_OWNER, FINRAG_API_TOKEN and GENERATOR_MODEL through an ignored runtime env file.
# GPT-6 Luna uses REASONING_EFFORT=none (the old minimal value is rejected).
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 finrag-private
# Process one pending job in the same environment/image; schedule a bounded invocation later.
docker run --rm --env-file .env finrag-private python scripts/sources.py worker
```

Run `sources.py migrate` explicitly before startup. A TLS database connection is required across hosts; same-host/private Docker networking must never publish the database port. Use a token generated outside logs, rotate it as a single-owner credential, and keep `.env` outside the image/version control. The private factory fails without token/DSN. No cloud resources, secrets or scheduled tasks are created by this implementation.

## Capacity and budget

- One API process, at most two concurrent requests, one ingestion worker. Uvicorn's threshold is `3` because it rejects at `>= limit`; the Docker check confirms two simultaneous queries return 200. Request-scoped query pipelines prevent shared filter/source mutation. SQL connections are opened for bounded operations and closed immediately, with five-second connect/lock and 30-second statement timeouts. Limit PostgreSQL to a small connection budget (for example 12 connections) and keep the worker count at one.
- Upload/snapshot ≤20 MiB; PDF page selection ≤100; build ≤3,000 children; BM25 corpus ≤10,000 children; queries ≤4,000 characters and generation ≤4,096 completion tokens with a 60-second timeout/no automatic retry. Defaults omit VLM captions; raw table/text evidence remains intact. Expensive chart captioning requires an explicit supplied captioner and a reviewed budget.
- Snapshot deadline 30 seconds, DNS timeout five seconds, three redirects, no remote subresources/browser rendering. Embeddings timeout at 60 seconds with at most two retries. Jobs have a 15-minute lease; failed/expired work must retain the last good build. The finite one-job CLI invocation is the recovery/scheduler boundary.
- Context experiments cap each document at 1,000 children/120,000 characters and batch at most 48 children. Metadata uses at most 120,000 characters and 2,500 completion tokens per unresolved version. Both use timeout/no automatic model retry and persist reusable results. Unknown model pricing cannot pass a paid promotion gate; configure verified pricing before claiming a dollar budget.
- LangSmith tracing is off unless the operator explicitly sets `FINRAG_ALLOW_TRACING=true`. Do not enable source text traces for private financial content without a separate retention/access decision. The API suppresses access logs; errors persist stage/class rather than request content or credentials. Evaluation is offline and separately budgeted.



## Readiness, restart, restore and failure recovery

Authenticated `/health` distinguishes database access from searchable readiness. An empty registry is live but unready. An incompatible active embedding profile rejects load/retrieval; a new profile needs a separate completed build. Startup reads SQL/private objects and needs no pickle or warm local index. Exact search avoids an ANN build/cold-start dependency. Maintain an SSH-only readiness probe with the bearer token outside command/log history.

Back up SQL (including registry, chunks/vectors, usage and review state) with `pg_dump`, retain immutable raw objects/versioned bucket backups, and test restore into a separate database. Restore SQL first, run `sources.py migrate` for an older schema, verify all referenced object hashes/access, then start the same embedding profile. Never replace the live database until the restored query/evidence checks pass. A backup that excludes raw objects is incomplete.

The disposable integration check restores a SQL dump into a second database and retrieves the same original evidence with offline query vectors; it also proves owner isolation, archive exclusion and last-good retention. `python -m pytest tests/unit/test_private_runtime.py` verifies dependency isolation and no legacy-app initialization.



## Notebook and local compatibility path

Seven notebooks teach parsing, chunking, retrieval, generation and offline evaluation. These commands can make paid embedding/model calls; reuse valid cached outputs and budget new work explicitly.

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

These commands do not select persistent Research unless `DATABASE_URL` is configured. `scripts/run_eval.py` is an offline diagnostic; [BENCHMARK](EVALUATION.md) owns manifested experiments/replay. Retained notebook outputs and ignored raw CSVs are historical experiments, not current Ask/research accuracy or a latency SLA.



## Original teaching PDFs

- [Wells Fargo Q4 2025](https://www.wellsfargo.com/assets/pdf/about/investor-relations/earnings/fourth-quarter-2025-earnings.pdf)
- [Tesla Q1 2026 update](https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q1-2026-Update.pdf)
- [AMD Q4 2025 slides](https://d1io3yog0oux5.cloudfront.net/_b0eb9fe85e9ee1621001cc760a9e1d73/amd/db/841/9223/presentation/AMD+Q4%2725+Earnings+Slides+FINAL.pdf)
