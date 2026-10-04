# Durable decisions

[STATE](STATE.md) owns completion/status; [INDEX](INDEX.md) owns the current plan registry. Decisions describe why a choice persists, without implying new work is authorized.

| Decision | Status | Reason and authority |
| --- | --- | --- |
| One existing service/query graph, Postgres/pgvector and private originals | current | Stable source/version/build identity, authorized pinned snapshots and atomic last-good publication. No separate agent/search platform is justified. [Persistence](PERSISTENCE.md), [architecture](kb/ARCHITECTURE.md) |
| Parent-child + BM25/RRF | current | Controlled contextual prefixes and SQL lexical ranking did not improve final evidence within the fixed budget. [Negative screens](RETRIEVAL_RESULTS.md) |
| Positive `supplement_k` is an opt-in quote/calculation protocol; default zero | held experiment | Quote-bound capture improved recall but lost strict/numeric correctness and exceeded cost allowance. [Phase-close results](PHASE_CLOSE_REPORT.md#subsequent-financial-evidence-implementation) |
| Deterministic identity, filters, coverage, periods, arithmetic and receipt accounting | current | Models may propose ambiguous metadata or a bounded narrative; they cannot certify facts, permission, comparability or their own claims. [Research](kb/RESEARCH.md), [usage](USAGE.md) |
| Original support and named semantic review authorize financial operands | current | Exact locations alone do not prove row/period/scope/basis meaning. Generated captions, candidates and narrative drafts stay separate. [Evidence](EVIDENCE.md), [metric policy](PRODUCT_METRIC_POLICY.md) |
| Reopen immutable history; explicit rerun creates another result | current | Preserve original answers and pins; distinguish evidence changes, result changes and failed refresh. Watchlist is a saved selection, without monitoring. [Research/history](kb/RESEARCH.md) |
| Deep three-company histories; frozen 18-primary + four-companion development inventory | current | Completed local corpus supports scoped comparisons without broad acquisition or economic-equivalence claims. [Inventory](fixtures/product/development_inventory.v1.json), [metric policy](PRODUCT_METRIC_POLICY.md) |
| Keep independent review, disjoint holdout and frozen gates separate from development | current | Mechanical success and Codex review cannot establish strict release accuracy. Holdout tuning spends the holdout. [Evaluation contract](PHASE_3_EVALUATION.md) |
| Planner, public hosting and scheduled refresh | deferred | Evidence/decomposition and access/capacity prerequisites remain. [Release plan](plans/RELEASE_VALIDATION.md#deferred-boundaries) |
| INDEX → STATE → indexed plans → decisions/KB → dated evidence | current | One current truth and one update workflow. Extract durable content, fix links and delete obsolete coordination docs. [CONTRIBUTING](../CONTRIBUTING.md) |

## Superseded proposals

- The original registry investigation and its 12 draft implementation boundaries are complete as local implementation/Docker work. Their old missing-registry architecture is superseded by [Persistence](PERSISTENCE.md); measured quality failures remain in [phase-close evidence](PHASE_CLOSE_REPORT.md).
- Phase 3 M1–M4 contracts/observations/calculation/workflow and M6 workspace are implemented locally. Their “build next” proposals and old missing-history descriptions are superseded by [STATE](STATE.md) and [Research](kb/RESEARCH.md). M6 release gates remain open; M5 planning remains deferred.
- Product batches A–C acquisition, local runtime, reviewed development cards, guided UI and development captures are complete. Earlier 14-file inventory, Tesla acquisition gaps, missing DATABASE_URL and development budget/review handoffs are superseded by tracked [acquisition](fixtures/product/acquisition_receipts.v1.json), [ingestion](fixtures/product/ingestion_receipts.v1.json), [reviewed cards](fixtures/product/reviewed_observations.v1.json) and [development results](PRODUCT_DEVELOPMENT_CAPTURE.md).
- The initial product corpus estimate of 120–180 cards is replaced by 168 retained cards. The 2021 holdout reserve and public-demo budget targets were planning assumptions, not sealed evidence or provisioned capacity; only the [remaining release plan](plans/RELEASE_VALIDATION.md) carries them where still useful.

Obsolete planning/review/progress/handoff files are deleted after consolidation. Git history retains their original wording; immutable benchmark inputs, manifests, results, review overlays, patches and receipts remain at their original paths.
