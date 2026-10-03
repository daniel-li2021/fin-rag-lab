# Low-cost private deployment profile

This is a prepared profile, not a provisioned deployment. The selected behavior is existing parent-child retrieval plus BM25; contextual hints and PostgreSQL lexical ranking remain opt-in pending their promotion gates. `Dockerfile.private` includes only application code and the separate durable runtime requirements. Corpus updates go through the registry/object store and require no image rebuild. Chroma, Streamlit, notebook/evaluation/test dependencies are omitted from this runtime.

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

## Idle and request estimate

Estimate checked October 2, 2026, for an ordinary US-region Linux/IPv4 Lightsail bundle; no promotional credits. [AWS's Lightsail price table](https://aws.amazon.com/lightsail/pricing/) lists 2 GB/2 vCPU/60 GB at $12/month, a 5 GB/25 GB-transfer object-storage bundle at $1/month, and instance snapshots at $0.05/GB-month. With 10 GB of snapshots, `Decimal('12') + Decimal('1') + Decimal('10') * Decimal('0.05')` gives **$13.50/month idle**. The small self-managed Postgres runs on that VM. This is a capacity assumption to validate, not a measured memory benchmark; the 4 GB bundle is $24/month if the complete process set does not fit.

The included bundle allowances cover a small workload; overages, taxes, optional domain/logging/secret services, extra backup copies and external object/database egress are additional. A standard S3 bucket is an alternative with regional storage/request pricing ([AWS S3 pricing](https://aws.amazon.com/s3/pricing/)); do not substitute it into the $1 Lightsail bucket estimate without recalculating.

For 1,000 queries averaging 5,000 ordinary input and 1,000 total completion tokens, the October 2 verified [Luna tariff](https://developers.openai.com/api/docs/models/gpt-6-luna) gives **$1.00** (input $0.10/M, output $0.50/M). Reported cache reads/writes use their separate tariffs; reasoning is part of completion tokens. The [completed benchmark](PHASE_CLOSE_REPORT.md) measured **$0.019366155 for 30 queries**, including actual cache-write tokens and fresh query embeddings. Its frozen pricing/receipt sidecar is separate from the application's approximate default price table. Add ingestion/contextualization, optional judging and infrastructure separately; this is a token-based charge calculation, not invoice reconciliation.

## Readiness, restart, restore and failure recovery

Authenticated `/health` distinguishes database access from searchable readiness. An empty registry is live but unready. An incompatible active embedding profile rejects load/retrieval; a new profile needs a separate completed build. Startup reads SQL/private objects and needs no pickle or warm local index. Exact search avoids an ANN build/cold-start dependency. Maintain an SSH-only readiness probe with the bearer token outside command/log history.

Back up SQL (including registry, chunks/vectors, usage and review state) with `pg_dump`, retain immutable raw objects/versioned bucket backups, and test restore into a separate database. Restore SQL first, run `sources.py migrate` for an older schema, verify all referenced object hashes/access, then start the same embedding profile. Never replace the live database until the restored query/evidence checks pass. A backup that excludes raw objects is incomplete.

The disposable integration check restores a SQL dump into a second database and retrieves the same original evidence with offline query vectors; it also proves owner isolation, archive exclusion and last-good retention. `python -m pytest tests/unit/test_private_runtime.py` verifies dependency isolation and no legacy-app initialization.

Issue 12's October 2 Linux/arm64 Docker validation is complete: a 146.11 MiB image starts without lab-only dependencies, restores SQL plus three verified raw objects, rejects missing auth/foreign owners, serves two concurrent live queries, and survives API/database restart and fresh-container recreation. A bounded worker activates and queries a new Markdown source/version without an image rebuild. Measured cgroup peaks are API **205.16 MiB**, DB **114.40 MiB**, worker **232.94 MiB**, each under a 512 MiB cap with no OOM. Restart/recreation to authenticated ready took 0.493–2.148 seconds. [Receipts and measurements](DOCKER_CHECK.json), [phase-close report](PHASE_CLOSE_REPORT.md).

The sum of separate observed peaks is 552.50 MiB; it supports the 2 GB VM as a capacity candidate for this corpus. It is not simultaneous process-set measurement or a sustained-load/worst-case PDF-ingestion test. Linux/amd64, VM OS overhead and actual private-bucket permissions remain deployment checks. No cloud resources were provisioned.
