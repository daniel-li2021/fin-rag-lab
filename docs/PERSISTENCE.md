# Durable sources

The Postgres backend is opt-in. The notebook/Chroma service remains available when `DATABASE_URL` is absent. Install `requirements-persistence.txt` alongside the existing lab dependencies, or use `requirements-private.txt` for the API/worker only. PostgreSQL 13+ with pgvector is required; the checks use a disposable Postgres server and pgvector 0.6.2.

```sh
# Supply DATABASE_URL, FINRAG_OWNER and OPENAI_API_KEY through an ignored env file/environment.
python scripts/sources.py migrate
python scripts/sources.py register --kind markdown --title 'Financial note' --locator note.md
python scripts/sources.py ingest --source-id SOURCE_UUID --file note.md
python scripts/sources.py query --question 'What revenue was reported?' --filters '{"source_id":"SOURCE_UUID"}'
python scripts/sources.py list
python scripts/sources.py archive --source-id SOURCE_UUID
```

`migrate` is an explicit, idempotent initial schema migration, including compatibility columns for the early prototype. Ordinary service startup does not migrate automatically. The database role must be limited to this application database; authenticated owner scoping occurs on every registry, job, object-download and retrieval path. No request may supply an owner. This first private profile deliberately has one owner/bearer token; it does not implement a public multi-user identity system.

Phase 3 adds `financial_observations`, `research_collections` and `research_runs` through the same migration. Reviewed observation IDs and saved-run payloads are immutable; new reviews/reruns receive new identities. Collections retain stable source IDs, while each run retains resolved versions/builds and metadata revisions. The saved owner can reopen historical answers after source updates or archives; new retrieval/reruns still enforce archive/owner checks. [Workspace and routes](PHASE_3_IMPLEMENTATION.md).

## Identity, metadata and lifecycle

Registration creates a stable source UUID and does no parsing, embedding or URL fetching. Supported kinds are PDF, UTF-8 text, Markdown and URL. Titles never deduplicate sources. A repeated owner/request key returns the same source only when the immutable original registration fingerprint agrees; conflicting reuse is rejected. Later metadata confirmation cannot break a retry or be overwritten by it. Early prototype rows without a fingerprint bind their first compatible retry while preserving existing metadata. Display filenames are reduced to their basename and never serve as filesystem paths or storage keys.

Raw bytes are stored at `SHA256(owner)/SHA256(bytes)` in a private object directory or S3-compatible bucket. Objects validate their hash on reading; identical bytes in one authorized scope share a blob but retain separate registered source IDs. `FINRAG_BUCKET` selects the S3 adapter; otherwise `FINRAG_OBJECT_DIR` selects a private local object directory. Local objects are the development/restore reference; a disposable cloud filesystem requires private object storage. Writes that precede a failed SQL transaction can leave unreferenced objects. Retain them for a seven-day grace period and inspect SQL references before operator cleanup; there is no automatic object deletion.

Versions have monotonic numbers, complete content hashes, raw media/size/provenance, original metadata snapshots and supersession links. Retrying unchanged bytes/configuration reuses the version/build/job. The build manifest pins embedding model/dimensions/distance, parser configuration and derived-code hash, captioner, chunk sizes/overlap, PDF page cap/range and evidence revision. It never infers an embedding model from vector dimensions.

Document-cache keys include loader/parser/captioner classes, public scalar settings and their source-code hashes. Older cache entries without this configuration are reparsed; matching text/model embedding caches remain reusable.

A leased job parses and embeds outside SQL transactions, validates the complete evidence/chunk/vector set, then publishes all derived rows and active pointers in one transaction. Publication checks the current lease; archive or a newer requested build wins over a late worker. One source update preserves the other sources. Errors record the failing stage/exception class and usage, and keep the previous active build searchable. A 15-minute expired lease can be reclaimed; completed jobs are idempotent. `scripts/sources.py worker` processes one eligible job, or accepts `--job-id` for an explicit retry. It never spins indefinitely or retries failed jobs automatically. The worker must use the same manifest configuration as the submission.

Company, fiscal period and business document type are explicit metadata, separate from format. Unknown remains null/unknown. Financial filters require `review_status=confirmed`. A different content version preserves field values but marks its snapshot as needing review; publishing it requires re-confirmation for financial filtering unless the user explicitly updated metadata after submission. A failed refresh does not remove the old confirmed active metadata. Historical explicit-version filters use the latest confirmed append-only version metadata review, falling back to the immutable registration-time snapshot. A review requires the exact source/version, reviewer and reason; it preserves raw bytes and previous metadata. Current source corrections remain authoritative for the active source. Research may pin a metadata review ID alongside version/build IDs; it never borrows another version's quarter. See [Phase 3 research](PHASE_3_IMPLEMENTATION.md).

`POST /sources/{id}/suggestions` first resolves explicit flat front-matter field labels without a model, then invokes Luna for remaining unresolved company name/year/quarter/document type, validates supporting original block quotes and caches the result by input/model/prompt/current metadata. It returns a version ID for review and never merges sources, supplies a canonical company ID, or changes confirmed fields. A confirmed metadata snapshot skips the model entirely. Six synthetic labeled cases and abstention results are saved in `METADATA_CHECK.json`; these are a smoke screen, not a financial metadata accuracy guarantee.

## Source handling and evidence

Text/Markdown use strict UTF-8, reject NUL/empty/oversize input, preserve Markdown heading paths and exact original line offsets, and need no PDF parser/VLM/classification call. Static HTML removes script/style content; lines refer to the extracted snapshot text, whose raw HTML remains downloadable. Dynamic rendering, crawling, login pages and remote subresources are outside this adapter.

A URL registration is a bookmark, with no searchable content. Explicit snapshot fetching permits standard-port HTTP(S), checks every DNS result and redirect for non-public addresses, pins the actual connection to a checked address, retains TLS hostname verification, and caps DNS timeout, transfer deadline, redirects and raw bytes. Unsupported/compressed media fail clearly. Original/final URL, retrieval time, ETag/Last-Modified and hash are retained. Same-byte snapshots incur no new build; fetch failures retain active content. Fetching makes no browser or model call.

Retrieval resolves owner, active source/version/build and confirmed business filters in a repeatable-read SQL snapshot before vector/lexical fusion. Exact cosine pgvector search and relational parents require compatible model/dimensions/input hashes. BM25 remains the compatibility default, with a hard 10,000-child corpus limit. PostgreSQL GIN-backed `simple` text search/`ts_rank_cd` is a measured opt-in branch, not a claim of BM25 equivalence. Archive immediately excludes a source, including explicitly requested historical versions. Citations retain source UUID, immutable content hash, version UUID, block offsets, pages/lines and original evidence. Retrieved cards do not become answer citations. Confirmed business metadata is attached only to request-local chunk copies from the same authorized source/version snapshot; explicit historical versions use reviewed version metadata when available. Stored evidence is not rewritten.

## API, UI and migration

Set `DATABASE_URL` and a random `FINRAG_API_TOKEN` of at least 24 characters to select the private API from `src.api.server`. The private image starts `src.api.private_server:build_private_app --factory` and fails closed when credentials are missing. All endpoints, including health, require `Authorization: Bearer TOKEN`.

- `POST/GET /sources`; `GET /sources/{id}` and `/versions`.
- `PATCH /sources/{id}/metadata` confirms a complete validated metadata object; `DELETE /sources/{id}` archives.
- `POST /sources/{id}/content` accepts raw bytes with the appropriate Content-Type and returns a durable job ID. A separate worker processes it.
- `POST /sources/{id}/snapshot` captures/queues a URL snapshot; `GET /jobs/{id}` exposes status/attempts/error/usage.
- `GET /sources/{id}/versions/{version_id}/raw` returns an authorized attachment with no-store/nosniff headers.
- `POST /query` accepts `question`, optional `filters` (source/version/company/year/quarter/document type) optional verification and `supplement_k` (strict integer 0–8, default 0). Positive values enable the experimental bounded-parent evidence and quote/calculation response profile; it is not promoted for default use.

There is no arbitrary-server-path `/ingest` endpoint in the private app. Streamlit with `DATABASE_URL` opens Research and exposes Library, History and Ask. Registration, upload/refresh, metadata editing, archive and reviewed fact import live under Owner administration; Ask has a separate source selector. Keep Streamlit local or behind an authenticated SSH/private proxy; bearer authorization belongs to the API profile.

`scripts/migrate_index.py --output /tmp/migration-map.json` registers the raw PDFs explicitly and saves an old document-ID → source/version/hash mapping after each completed source. It reuses local vectors only when the saved model, evidence revision, vector dimensions and exact embedding inputs all agree. The existing pre-foundation index lacks model provenance, so its vectors require a bounded rebuild from raw PDFs and valid embedding caches. Trusted local pickle import is never exposed to uploads. The original local index is not overwritten.

Validation: `python -m pytest tests/unit/test_sources.py tests/unit/test_contextual_metadata.py tests/integration/test_persistent.py`. The database tests require optional `pgserver` (or adapt the fixture to a disposable PostgreSQL database); they use offline vectors, test competing claims and failed publication, exercise authenticated API uploads, and restore a SQL dump into another database while verifying referenced object hashes. Deployment constraints: [private profile](PRIVATE_DEPLOYMENT.md).
