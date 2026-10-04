# Persistent local authentic development runtime

The October 3 authorization allows authentic acquisition, paid embeddings, regression and development captures on local Postgres. Cloud/public deployment remains deferred. The planner stays disabled. Codex may resolve clear bindings against original evidence and the metric policy; record the reviewer as Codex, not an independent human reviewer. Genuine unresolved semantic or policy questions require a concise evidence packet and recommendation. Development review does not satisfy the separate independent release gates.

Start or reuse the installed `pgserver` development runtime:

```sh
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/local_postgres.py status
set -a
source index/product-local/runtime.env
set +a
.venv/bin/python -m streamlit run app/streamlit_app.py
```

The ignored profile contains the database connection and owner, never a copied API key. The app continues to read the existing ignored `.env`. The cluster and objects live under ignored `index/product-local/`; the directory is private, the server listens only on a Unix socket, and `finrag_app` has no superuser, database-creation or role-creation privilege. `start` is repeatable and retains identities; process exit does not stop Postgres. `stop` performs a normal shutdown and retains the cluster. This is a local development runtime, without an automatic reboot launch agent or backup service.

The frozen acquisition inventory remains unchanged. `acquisition_resolutions.v1.json` records official issuer alternatives, including Tesla's PDF copies of the same SEC filings and issuer-hosted shareholder decks. Receipts preserve the original URL, actual acquisition/final URLs, bytes hash and physical PDF page count. Alternative renderings are not assumed byte-equivalent. All 22 development originals are retained; none of that alone authorizes financial facts or authentic accuracy claims. No holdout sources or labels are acquired by these commands.

```sh
SSL_CERT_FILE=$(.venv/bin/python -m certifi) .venv/bin/python scripts/prepare_product_corpus.py --acquire
```

The reviewed physical windows and metadata are in `indexed_windows.v1.json`; partial coverage remains visible. `.venv/bin/python scripts/ingest_product_corpus.py` validates every inventory, window and original hash without model calls. Add `--ingest` for actual embeddings; the worker reuses completed builds and cached embeddings, stages each build and atomically activates it. Job/build IDs, actual API usage, configured cost estimates and per-report wall time are retained in `ingestion_receipts.v1.json`. The application never treats the candidate review packet as ingestion blocks.

Next gates are immutable metric bindings, frozen development labels and captures with measured model usage, latency and cost. The separate 48-question holdout remains inaccessible to development work.
