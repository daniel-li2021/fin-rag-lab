# Documentation index

Start with [STATE](STATE.md) for current behavior, evidence limits and the next work item. Follow [CONTRIBUTING](../CONTRIBUTING.md) for implementation, documentation updates and integration. [README](../README.md) is the runnable introduction; [AGENTS](../AGENTS.md) is the short agent entrypoint.

Authority: current behavior is described by STATE and the linked code/contracts; plans describe intended work; decisions explain retained choices; dated results describe only their captured configuration. When they disagree, verify the code and receipts, then correct STATE. A merged implementation does not imply release-quality validation or deployment.

## Active plans

Each current plan must appear here with its status, purpose and next action. Multiple plans may run concurrently when their scopes and dependencies are explicit. Use `active`, `blocked`, `planned` or `complete`; explain any blocker. A completed plan leaves this table after its durable findings are consolidated.

| Plan | Status | Purpose | Next action |
| --- | --- | --- | --- |
| [Release validation](plans/RELEASE_VALIDATION.md) | active; release blocked on independent review and holdout custody | Close authentic evaluation and matched historical gates for the existing local prototype | Review the retained full historical control before deciding whether another capture or code change is needed |

The planner, public hosting and scheduled refresh are deferred decisions, not active implementation plans.

## Durable decisions and knowledge

| Home | What to trust it for |
| --- | --- |
| [Decisions](DECISIONS.md) | Current choices, their evidence and explicitly superseded proposals |
| [Architecture](kb/ARCHITECTURE.md) | Current execution paths, storage boundaries and responsible modules |
| [Research contracts and routes](kb/RESEARCH.md) | Pinned facts, calculations, evidence search and immutable history |
| [Local development runtime](PRODUCT_LOCAL_RUNTIME.md) | Reuse of the existing private Postgres corpus and loopback UI |
| [Persistence](PERSISTENCE.md) | Registry identity, atomic publication, private API and restore semantics |
| [Evidence](EVIDENCE.md) / [usage](USAGE.md) | Original provenance, outcomes and known/unknown receipt semantics |
| [Metric policy](PRODUCT_METRIC_POLICY.md) | Financial definitions, comparability and review authority |
| [Notebook and compatibility usage](kb/NOTEBOOKS.md) | Teaching path, legacy local commands and scoped historical notebook results |
| [Private deployment profile](PRIVATE_DEPLOYMENT.md) | Prepared operating limits; local Docker evidence, without a cloud deployment claim |

## Evidence and reproducibility

| Record | Scope |
| --- | --- |
| [Benchmark contract](BENCHMARK.md) | Frozen labels, capture/replay and retrieval promotion rules |
| [Phase 3 evaluation contract](PHASE_3_EVALUATION.md) | Frozen authentic release gates and legacy diagnostic-fixture scope |
| [Development capture](PRODUCT_DEVELOPMENT_CAPTURE.md) | 22-source/168-card development corpus, frozen 48 cases, historical control and local demonstration |
| [Development results ledger](benchmarks/20261003-product-development/README.md) | Four immutable captures, failures, review qualifications and usage |
| [Retrieval results](RETRIEVAL_RESULTS.md) | Retained parent-child/BM25 decision and negative contextual/SQL screens |
| [October 2 phase-close report](PHASE_CLOSE_REPORT.md) | Historical 30-question review, subsequent failed experiments and local Docker validation |
| [Benchmark directories](benchmarks/) / [fixtures](fixtures/) / [screenshots](screenshots/) | Immutable manifests, raw results, review overlays, hashes and actual local screenshots |

JSON check records beside this index retain their dated scopes: [contextual](CONTEXTUAL_CHECK.json), [lexical](LEXICAL_CHECK.json), [metadata](METADATA_CHECK.json), [live smoke](LIVE_CHECK.json), [Docker](DOCKER_CHECK.json). Ignored originals, caches and local databases are not distributed by a fresh clone; tracked manifests identify what must be reproduced.
