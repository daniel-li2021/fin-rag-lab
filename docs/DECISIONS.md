# Durable decisions

[STATE](STATE.md) owns status; [NEXT_WORK](NEXT_WORK.md) owns pending work. Captured results are linked directly, without standalone historical reviews/plans.

| Choice | Status and basis |
| --- | --- |
| Existing service/query graph + Postgres/pgvector/private originals | current: owner-scoped immutable identity, pinned snapshots and atomic last-good builds; no separate agent/search platform. [System](kb/SYSTEM.md) |
| Parent-child + BM25/RRF | current: fixed-budget [contextual screen](evidence/checks/CONTEXTUAL_CHECK.json) failed final-recall promotion; [SQL lexical screen](evidence/checks/LEXICAL_CHECK.json) lost recall despite 30/30 vector-ranking parity. Better child rank alone is insufficient. |
| Positive `supplement_k`, default zero | held experiment: [quote-bound paired capture](benchmarks/20261002-financial-answers-bound/paired_summary.json) gained recall but lost strict/numeric correctness and exceeded [cost allowance](benchmarks/20261002-financial-answers-bound/measured_cost.json). A valid quote location/title citation does not prove claim support. |
| Deterministic identity/filter/coverage/period/arithmetic/receipt logic | current: bounded models may propose metadata or draft narratives; they cannot authorize evidence or certify their own claims. [Evidence](kb/EVIDENCE.md) |
| Reviewed original bindings and explicit financial definitions | current: respect attribution, fiscal intervals, accounting basis, continuing operations and revision lineage. Generated captions/candidates are not operands. [Financial policy](kb/FINANCIAL_POLICY.md) |
| Immutable history + explicit separate reruns | current: preserve answers/pins and distinguish byte/build/metadata changes, changed results and failed refresh. Watchlists are saved selections without monitoring. [System](kb/SYSTEM.md) |
| Frozen three-company development corpus; separate independent release gates | current: 18 primary + four companion originals, named Codex review and mechanical checks do not establish independent authentic accuracy. Holdout tuning retires that holdout. [Evaluation](kb/EVALUATION.md) |
| Planner | deferred: first pass deterministic authentic gates and identify at least five supported decomposition/routing failures where explicit tasks succeed. A fresh planner evaluation must add at least three strict holdout successes without losses and meet unchanged safety/budget bounds. |
| Public hosting, scheduled refresh and broad feature expansion | deferred: public use needs server-enforced read-only access, TLS/auth, isolated data, server-only secrets, session isolation, disabled upload/fetch/review/admin routes and hard request/model allowances. Measure full expanded-process capacity. Consider frontend rewrite, new companies/XBRL/ANN, automatic semantic promotion or general formulas only for a measured requirement. |

## Supersession and document ownership

Registry implementation, reviewed local histories/cards, calculations, saved history, guided UI and development capture are implemented; earlier missing-registry, missing-database, acquisition-gap and “build next” prose is superseded by STATE and current KB. Failed/partial experiments remain held in their original artifacts; development completion does not supersede independent release gates.

INDEX → STATE → NEXT_WORK → decisions/KB → immutable evidence is the documentation structure. Only actively pending work belongs in NEXT_WORK. Extract useful content and delete obsolete plans, reviews, investigations, checkpoints, handoffs, progress files and redundant Markdown result summaries; Git retains original wording. Keep artifact bytes/hashes and captured policy identifiers intact. Generated checks live under `docs/evidence/checks/`; no generated evidence or historical document library belongs in the docs root. [Update workflow](../CONTRIBUTING.md).
