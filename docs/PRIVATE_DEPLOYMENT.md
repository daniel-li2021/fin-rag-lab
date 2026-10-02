# Low-cost private deployment profile

This is a prepared profile, not a provisioned deployment. The selected behavior is existing parent-child retrieval plus BM25; contextual hints and PostgreSQL lexical ranking remain opt-in pending their promotion gates. `Dockerfile.private` includes only application code and the separate durable runtime requirements. Corpus updates go through the registry/object store and require no image rebuild. Chroma, Streamlit, notebook/evaluation/test dependencies are omitted from this runtime.

Use one small Linux Lightsail VM, one PostgreSQL/pgvector process on a persistent volume, and a private S3-compatible bucket. The application container is disposable; the database volume and bucket are not. This is a single-node private profile with an operator-managed database, not high availability. Keep PostgreSQL off public interfaces and the API reachable through an SSH tunnel/private authenticated proxy. Do not add an ALB, NAT gateway or public database for this tiny corpus. Configure private bucket access and scoped AWS credentials before an eventual deployment.

```sh
# Preparation only; run when deploying is explicitly requested.
docker build -f Dockerfile.private -t finrag-private .
# Supply DATABASE_URL, FINRAG_BUCKET, AWS_DEFAULT_REGION, OPENAI_API_KEY,
# FINRAG_OWNER, FINRAG_API_TOKEN and GENERATOR_MODEL through an ignored runtime env file.
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 finrag-private
# Process one pending job in the same environment/image; schedule a bounded invocation later.
docker run --rm --env-file .env finrag-private python scripts/sources.py worker
```

Run `sources.py migrate` explicitly before startup. A TLS database connection is required across hosts; same-host/private Docker networking must never publish the database port. Use a token generated outside logs, rotate it as a single-owner credential, and keep `.env` outside the image/version control. The private factory fails without token/DSN. No cloud resources, secrets or scheduled tasks are created by this implementation.

## Capacity and budget

- One API process, at most two concurrent requests, one ingestion worker. Request-scoped query pipelines prevent shared filter/source mutation. SQL connections are opened for bounded operations and closed immediately, with five-second connect/lock and 30-second statement timeouts. Limit PostgreSQL to a small connection budget (for example 12 connections) and keep the worker count at one.
- Upload/snapshot ≤20 MiB; PDF page selection ≤100; build ≤3,000 children; BM25 corpus ≤10,000 children; queries ≤4,000 characters and generation ≤4,096 completion tokens with a 60-second timeout/no automatic retry. Defaults omit VLM captions; raw table/text evidence remains intact. Expensive chart captioning requires an explicit supplied captioner and a reviewed budget.
- Snapshot deadline 30 seconds, DNS timeout five seconds, three redirects, no remote subresources/browser rendering. Embeddings timeout at 60 seconds with at most two retries. Jobs have a 15-minute lease; failed/expired work must retain the last good build. The finite one-job CLI invocation is the recovery/scheduler boundary.
- Context experiments cap each document at 1,000 children/120,000 characters and batch at most 48 children. Metadata uses at most 120,000 characters and 2,500 completion tokens per unresolved version. Both use timeout/no automatic model retry and persist reusable results. Unknown model pricing cannot pass a paid promotion gate; configure verified pricing before claiming a dollar budget.
- LangSmith tracing is off unless the operator explicitly sets `FINRAG_ALLOW_TRACING=true`. Do not enable source text traces for private financial content without a separate retention/access decision. The API suppresses access logs; errors persist stage/class rather than request content or credentials. Evaluation is offline and separately budgeted.

## Idle and request estimate

Estimate checked October 2, 2026, for an ordinary US-region Linux/IPv4 Lightsail bundle; no promotional credits. [AWS's Lightsail price table](https://aws.amazon.com/lightsail/pricing/) lists 2 GB/2 vCPU/60 GB at $12/month, a 5 GB/25 GB-transfer object-storage bundle at $1/month, and instance snapshots at $0.05/GB-month. With 10 GB of snapshots, `Decimal('12') + Decimal('1') + Decimal('10') * Decimal('0.05')` gives **$13.50/month idle**. The small self-managed Postgres runs on that VM. This is a capacity assumption to validate, not a measured memory benchmark; the 4 GB bundle is $24/month if the complete process set does not fit.

The included bundle allowances cover a small workload; overages, taxes, optional domain/logging/secret services, extra backup copies and external object/database egress are additional. A standard S3 bucket is an alternative with regional storage/request pricing ([AWS S3 pricing](https://aws.amazon.com/s3/pricing/)); do not substitute it into the $1 Lightsail bucket estimate without recalculating.

For 1,000 queries averaging 5,000 input and 1,000 total completion tokens, model charges are `5,000,000 * input_USD_per_token + 1,000,000 * output_USD_per_token`. Luna prices are not in the repository's verified price table, so the dollar result remains **unknown**, with raw usage retained. Reasoning is part of completion tokens. Add fresh embeddings, ingestion/contextualization and optional verification/judging separately; cache hits create no additional model call. Idle infrastructure plus this formula is the provider/request estimate, not a claim of zero model cost.

## Readiness, restart, restore and failure recovery

Authenticated `/health` distinguishes database access from searchable readiness. An empty registry is live but unready. An incompatible active embedding profile rejects load/retrieval; a new profile needs a separate completed build. Startup reads SQL/private objects and needs no pickle or warm local index. Exact search avoids an ANN build/cold-start dependency. Maintain an SSH-only readiness probe with the bearer token outside command/log history.

Back up SQL (including registry, chunks/vectors, usage and review state) with `pg_dump`, retain immutable raw objects/versioned bucket backups, and test restore into a separate database. Restore SQL first, verify all referenced object hashes/access, then start the same embedding profile. Never replace the live database until the restored query/evidence checks pass. A backup that excludes raw objects is incomplete.

The disposable integration check restores a SQL dump into a second database and retrieves the same original evidence with offline query vectors; it also proves owner isolation, archive exclusion and last-good retention. The API/model smoke checks run locally against the durable backend. `python -m pytest tests/unit/test_private_runtime.py` starts the private factory with notebook/evaluation/Chroma imports blocked and verifies that it never initializes the legacy app. Importing `src.api` now loads the local factory only on demand. Docker is not installed on this workstation, so the prepared image was not built here; build/start and resource sizing remain deployment-time validation. This is an explicit limitation, not a claim of a deployed or fully sized cloud runtime.
