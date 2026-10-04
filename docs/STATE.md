# Current project state

Updated October 3, 2026. Application baseline: [`79d76a1`](https://github.com/daniel-li2021/fin-rag-lab/commit/79d76a1f33f2141a00d5c2e27a0c3a36e09e1f60). This is the canonical current state; [INDEX](INDEX.md) lists current plans and [CONTRIBUTING](../CONTRIBUTING.md) owns the integration mode and update workflow.

## Implemented and locally demonstrated

- Persistent private Postgres/pgvector, immutable originals/versions, reviewed metadata, owner isolation, leased ingestion and atomic last-good build activation.
- Direct Ask with parent-child + BM25/RRF, structured outcomes, original citations and usage receipts. The quote/calculation response experiment requires positive `supplement_k`; default is zero.
- Research with task-scoped reviewed cards, pinned evidence, coverage/gaps, deterministic templates and cited Decimal calculations. Original passage search is bounded; optional one-call narrative drafts retain an unreviewed qualification.
- Research/Library/History in local Streamlit, named collections, immutable saved results, source-change indicators and separate explicit reruns. Source edits/imports are under trusted owner administration. Navigation is not public authorization.

The local development corpus contains **22 official originals** (18 primary + four companion reports/decks), **168 named Codex-reviewed fact cards**, **48 frozen development cases** and eight prepared collections. Physical indexed windows disclose omitted pages and preserve issuer fiscal dates. Numeric selection can use the 18-primary inventory without loading all passage blocks; passage search retains its 10,000-child bound. [Runtime](PRODUCT_LOCAL_RUNTIME.md), [metric policy](PRODUCT_METRIC_POLICY.md), [architecture](kb/ARCHITECTURE.md).

## Evidence boundary

| Retained evidence | Result | Qualification |
| --- | --- | --- |
| [Latest development capture](benchmarks/20261003-product-development/capture-v4/summary.json) | 48/48 mechanical checks; 25/25 numeric bindings; 48/48 exact history reopens | Development checks; strict authentic accuracy remains undefined |
| [Development claim review](benchmarks/20261003-product-development/development_claim_review.v1.json) | Eight narrative cases, including 12 generated claims and two supported refusals | Named Codex post-capture review, not independent release review |
| [October 3 historical control](benchmarks/20261003-product-regression/capture/summary.json) | 22/30 mechanical outcome matches | Full capture retained; strict semantic/numeric review and matched gates remain held |
| [October 2 historical baseline](PHASE_CLOSE_REPORT.md) | 19/30 strict; 9/10 numeric; 0/3 clarification; 4/4 OOC; 1/4 strict cross-document | Different captured configuration; not current research accuracy |
| [Local Docker check](DOCKER_CHECK.json) | Linux/arm64 auth, restore, restart, two-request concurrency and bounded worker checks | Earlier small corpus; not cloud, amd64 or expanded-corpus sustained capacity |

Four development captures retain their failures and exact labels/code hashes. Reported ingestion/control/development/live-rerun usage totals a configured **$0.05852726** estimate; one HTTP 400 attempt has unknown usage/cost. These are receipts and configured estimates, not an invoice. [Full ledger](benchmarks/20261003-product-development/README.md).

The old Phase 3 fixture remains a three-question diagnostic with zero eligible observations and no sealed cases; its checker validates that frozen fixture, not the newer 168-card/48-case development corpus. Development did not access the separate 48-case holdout; no populated, independently curated/sealed holdout or release results are demonstrated by these retained artifacts. Passing either integrity or mechanical checks does not satisfy authentic release gates. [Evaluation contract](PHASE_3_EVALUATION.md).

## Next work

Follow [release validation](plans/RELEASE_VALIDATION.md), beginning with independent review of the retained full historical control and release-critical original bindings. Reuse saved outputs before any new paid capture. Establish independent holdout custody/disjoint labels, then evaluate under the frozen gates; repair only demonstrated failures. Keep development and holdout denominators separate.

Release promotion is **held**. The planner is disabled. Public/cloud deployment, scheduled refresh, generic extraction and a frontend rewrite are deferred. The local development phase is complete; its earlier missing-database/acquisition/budget handoffs are obsolete. No new paid capture, holdout access or provisioning is authorized by this documentation cleanup.
