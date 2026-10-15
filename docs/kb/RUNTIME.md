# Runtime and reproduction

The [README](../../README.md) has install/start commands. Reuse the private local cluster, originals and matching caches; a fresh checkout needs verified acquisition, reviewed windows, explicit ingestion and original fact bindings before reproducing the corpus. [STATE](../STATE.md) owns corpus/results; [System](SYSTEM.md) owns lifecycle/API semantics.

## Local Postgres and Streamlit

The public portfolio uses the existing Meridian Next.js application in `frontend/`. It does not need this local database or a provider key. See [public hosting and progressive activation](#public-hosting-and-progressive-activation).

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

The earlier Lightsail/Postgres/private-bucket proposal remains a private alternative. The selected progressive public architecture is Vercel → authenticated Next.js adapter → Render FastAPI → Neon Postgres/pgvector plus private durable objects. No Render, Neon or object-storage resources have been provisioned for this release.

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

## Public hosting and progressive activation

**Deployment status:** Meridian is implemented and locally validated; initial Vercel import is being completed. The final deployment URL/status is recorded in [STATE](../STATE.md).

The single `frontend/` application retains Meridian's components, exact string-valued money, calculation receipts, source/version/build identities, citations and immutable execution/parent links. `lib/data-access.mjs` chooses the adapter per capability; `lib/demo.mjs` adapts explicitly approved captures into the existing FastAPI read contracts. `lib/relay.mjs` is the server-only bounded FastAPI adapter. Demo and Live use the same result, Evidence Inspector, Library and History views. A live failure never becomes a fabricated answer or silently relabeled saved result; Heroes remain separately available from the public archive.

The public archive contains five Heroes (ten steps), one AMD calculation and ten saved executions. One old-version query was never saved and stays outside History. Each of the eleven result payloads equals its frozen original; `npm test` validates artifact hashes, payload parity, public artifact screening and adapter/security behavior without a database/provider. Library is the union of sources/cards present in these captures, not the full owner corpus. Capture version IDs are retained; unexported registry ordinals, full metadata review logs and uncited cards are not invented. No collection contents are exported. Source-change status/comparison is a labeled preserved transition, not active refresh monitoring.

Full PDFs, rendered report pages, private data and backend secrets are excluded from the public deployment. Exact cited excerpts and role bindings remain inspectable; official source links replace local PDF delivery. One retained companion has no captured direct official URL and links to Tesla's quarterly disclosure directory with an explicit label. External issuers may change content or restrict access; the saved hash describes the retained capture, not a newly fetched web page. This does not authorize redistribution of entire reports.

Vercel project settings: connect `daniel-li2021/fin-rag-lab`, production branch `main`, **Root Directory `frontend`**, framework **Next.js**, install `npm ci`, build `npm run build`, output Next.js default, Node.js 22.x. Keep files outside the root excluded. `frontend/vercel.json` owns build/security headers; Root Directory is a project setting, not a `vercel.json` key. No static export, backend env vars, paid add-ons or deployment hooks are needed. The Git integration deploys main updates to the same production alias; other branches get previews. Required GitHub checks remain governed by repository settings; Vercel's Git deployment does not itself wait for unrelated Actions jobs. Roll back a failed release using Vercel's previous ready deployment. Do not publish `.env*`, `data/`, `index/`, caches or local originals.

Local public smoke path:

```sh
cd frontend
npm ci
npm test
npm run build
npm start -- --port 3250
# Separate terminal; no FastAPI, PostgreSQL or LLM needed.
FINRAG_SMOKE_URL=http://127.0.0.1:3250 npm run test:e2e
```

`test:live` / `test:api` are opt-in private compatibility scripts; they require the explicitly configured local backend and may create owner history. They are not the public demo check.

All five server-only flags default to `demo`: `FINRAG_RESEARCH_MODE`, `FINRAG_LIBRARY_MODE`, `FINRAG_HISTORY_MODE`, `FINRAG_COLLECTIONS_MODE`, `FINRAG_EVIDENCE_MODE`. Each accepts `live` independently; unknown values fail closed to Demo. `/api/backend/health` reports configuration only, not FastAPI readiness. The public UI labels preserved data; research/reruns are disabled in Demo and forbidden server-side. Admin, source registration/upload/snapshot/review/deletion, arbitrary query and collection writes are absent from the relay allowlist.

Minimal later activation, with separate resource/budget authorization:

1. Create Neon Postgres in the backend region; enable [pgvector](https://neon.com/docs/extensions/pgvector). Use a TLS direct connection initially: the current psycopg adapter sets connection startup `options`, so Neon transaction-pooler compatibility is not yet validated. Run `python scripts/sources.py migrate` with `DATABASE_URL` set privately. Restore a verified owner-scoped SQL dump including versions/builds/cards/history/vectors; validate schema and identity preservation. A fresh database alone has no reviewed corpus. Database residency/size and restore correctness must be checked before cloud activation.
2. Provide private durable originals, preserving every existing object key and SHA-256. The existing `FINRAG_BUCKET` path uses S3 and `AWS_DEFAULT_REGION`/scoped server credentials; it requires no object code change. Other S3-compatible endpoints, credentials and AES256 support require an explicit compatibility check before selection. Render's [free service filesystem is ephemeral](https://render.com/docs/free), so it cannot be the authoritative object store. A paid persistent disk is an alternative, not provisioned here.
3. Create a Render Python web service using `pip install -r requirements-private.txt`; start `uvicorn src.api.private_server:build_private_app --factory --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 3 --no-access-log`. Supply `DATABASE_URL`, `FINRAG_OWNER`, a strong `FINRAG_API_TOKEN`, object settings and the same embedding profile privately. The existing `Dockerfile.private` is an alternative with a Render command/port override. `/health` requires bearer auth; do not configure an unauthenticated Render probe against it. Check readiness from an authenticated operator client before enabling a capability. Operate one bounded worker (`python scripts/sources.py worker`) separately only for authorized ingestion; no public upload or scheduled refresh is enabled.
4. In Vercel, set the HTTPS `FINRAG_BACKEND_URL`, matching `FINRAG_API_TOKEN`, exact stable HTTPS `FINRAG_WORKSPACE_ORIGIN`, `FINRAG_WORKSPACE_USER` and a strong `FINRAG_WORKSPACE_PASSWORD`. None use `NEXT_PUBLIC_`. Live endpoints require HTTP Basic owner access before the server adds the separate backend bearer token. Sign in through `/api/backend/sources` after Library is enabled; the browser retains same-origin Basic authentication. This is a single-owner private gate, not visitor identity or multi-user authorization. Rotate credentials through hosting settings. Flip one capability to `live`, redeploy and check its actual owner/corpus/pin compatibility. Keep the others in Demo; set a failing capability back to Demo explicitly. Heroes stay public even when Render is offline. Before exposing any live capability anonymously, add a separately scoped public dataset/identity policy and hard quotas; flags alone must never remove this gate.
5. Activate fresh AI only after separately approving provider credentials, model/pricing, timeout and spending limits; keep them on Render. Retained passages/cards/vectors can be restored without fresh calls. Current paid narrative generation is private and bounded per call; anonymous unrestricted generation is not enabled. Validate a paid cloud request separately before claiming live generation works.

Initial hosting is expected to be **$0/month within Vercel Hobby allowances**, for this personal noncommercial portfolio. [Hobby terms/limits](https://vercel.com/docs/plans/hobby) apply; allowance exhaustion can limit service. No custom domain or paid resource was purchased. Future Render/Neon/storage/provider pricing and cold-start capacity need verification at activation. Render Free sleeps after inactivity and provides no durable local originals; the frozen demo avoids these dependencies. Independent financial review and sealed holdout gates remain held; public demonstration is not a new accuracy or production-capacity claim.

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
