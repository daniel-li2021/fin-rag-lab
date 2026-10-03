# Phase 3 implementation status

Phase 3 now has an opt-in, deterministic financial research path in the existing private service/API. It validates owner-reviewed observations against retained original blocks, pins source/version/build/hash identities in one database snapshot, checks required task coverage, and emits cited Decimal receipts or explicit gaps. Ordinary `/query` behavior and the held experimental answer profile remain unchanged.

| Milestone | Implemented | Still required |
| --- | --- | --- |
| M1 | Immutable financial request/period/evidence/observation/coverage contracts; failure mapping, split design, historical identities and offline integrity checker | Populate and independently review the authentic development/holdout corpus; agree a paid paired-capture budget |
| M2 | Original span/cell/page validation, six support roles, normalized value/unit checks; exact period/scope/basis and cutoff selection; explicit fact revision/conflict selection; append-only version metadata corrections | Resolve actual fiscal boundaries and other authentic binding gaps; independently review promoted facts; expand report/revision corpus |
| M3 | Difference, growth, percentage-point change, profit margin and delivery/production ratio; precision-100 Decimal normalization, half-up display, both operand citations and formula | Authentic q08/q22 receipts remain blocked by unresolved bindings; additive YTD/Q4/TTM derivations remain deferred |
| M4 | Explicit plans of up to six tasks, three companies and three periods; complete-candidate ranking; partial answers, conflicts, failed bindings and non-comparability; pinned numeric research export | Natural-language decomposition, narrative task retrieval, shared LangGraph routing and qualitative q25/q26 coverage; authentic release evaluation |
| M5 | Disabled; no planner calls | A sealed holdout and measured gain over M4 |
| M6 | Content-addressed JSON research export with request, manifest, review revisions, coverage, observations, receipts, citations and code hash | Named collections, persisted saved runs, staleness/rerun UI and release decision |

## Review authority

The private API is a single-owner trusted review surface. A submitted observation marked `reviewed` with a named `review_revision` is an **owner's manual semantic attestation** of metric, row/column, dates, scope and basis. The code independently checks original location, amount, unit and authorized source identity; it does not infer or certify those semantic associations. Do not submit model-written candidates as reviewed. Unreviewed or unresolved records cannot produce a numeric answer or calculation. These tests do not establish general extraction or narrative accuracy.

The six authentic [diagnostic cards](fixtures/phase3/authentic_observations.v1.json) preserve reviewed original locators but remain unverified. AMD and Tesla fiscal labels do not establish actual boundary dates; the Wells Fargo card also retains definition/basis/unit concerns. They yield **zero eligible authentic observations**. The three diagnostic questions are development-only; there are zero sealed holdout cases. The [evaluation contract](PHASE_3_EVALUATION.md) and [manifest](fixtures/phase3/manifest.json) freeze the design and historical inputs without inventing the planned 96 questions.

## Use

Apply the existing schema migration before using the new research or historical metadata-review routes:

```bash
python scripts/sources.py migrate
python scripts/check_phase3_evaluation.py
```

`POST /research` uses the existing bearer token and owner isolation. Supply `question` (a saved description), explicit `selections`, `tasks`, owner-reviewed `observations`, optional `calculations`, `mode` (`lookup`, `comparison`, `ranking`), `as_of` and `revision_policy`. The question is not interpreted as a plan: every intended candidate and operand must be a task. The full validated schema is in [research.py](../src/financial/research.py), [models.py](../src/financial/models.py) and the authenticated API schema.

For example, a request with a selected source but no reviewed fact returns coverage gaps rather than calling a model:

```json
{
  "question": "Q1 revenue in the selected report",
  "selections": [{"source_id": "<registered source UUID>"}],
  "tasks": [{
    "task_id": "revenue-q1", "company_id": "TEST", "metric_id": "revenue",
    "period": {"kind": "quarter", "start": "2026-01-01", "end": "2026-03-31",
               "fiscal_label": "Q1 2026", "calendar": "calendar"},
    "scope": "consolidated", "basis": "GAAP"
  }]
}
```

Selections may specify `version_id`, `build_id` and `metadata_review_id` to reuse historical artifacts. A build or metadata review requires its source version. Archived/foreign sources and mismatched versions/builds/reviews reject. Selected failed or unconfirmed sources appear in inventory and coverage rather than becoming zero observations. Source updates after snapshot loading cannot mix operands within a run. Existing failed-refresh/last-good behavior remains in effect.

`POST /sources/{source_id}/versions/{version_id}/metadata-reviews` accepts confirmed `metadata`, `reviewer` and `reason`; `GET` on the same route returns the append-only review history. Original version metadata/raw bytes remain intact. Explicit historical `/query` filters use the latest reviewed correction, while research can pin a particular correction. Corrections do not claim a financial restatement: fact revision selection requires original revision evidence and dimension-preserving predecessor links.

Differences and trends retain matching definitions, scope/basis and units. Cross-company differences require explicit `cross_company: true` and identical reporting intervals. Growth requires one company, distinct chronological periods and a positive baseline. A percent subtraction must use `percentage_point_change`. Unequal duration lengths require an explicit calculation `period_policy: reporting_kind` and are disclosed in the receipt. Margin uses reviewed gross profit, operating income or net income over same-period revenue; the named operating ratio uses deliveries over production. Zero/negative denominators, unknown dates, currency mismatch and unsupported metric pairs reject. No FX conversion or arbitrary formulas execute.

Store the returned JSON as the run artifact. Its `run_id` hashes the result content; it records source and review identities, inputs and derived receipts. This is an export, not server-side saved-run persistence or a guarantee that changed code produces an identical export. Keep the pinned originals for independent replay; an archived source remains inaccessible to new research.

## Validation and release boundary

Focused synthetic checks exercise Decimal scale/precision, percentage-point direction, compatibility, missing/conflicting facts, cutoff behavior, complete rankings and reproducible output. Disposable real Postgres/API checks exercise snapshot reuse across source updates, historical builds, metadata correction history, bearer auth, owner/version isolation and archive rejection; existing lifecycle checks retain failed-refresh and restore coverage. The offline evaluation checker validates hashes, original locators and split leakage without model calls.

Integrity passing is not answer-quality promotion. Current-default improvement, authentic holdout accuracy, extraction quality, model cost/latency and planner gain remain `not_assessable`; release remains **held**. No new ingestion, embedding/model/judge call, default promotion or cloud provisioning was performed. Next useful work is reviewed period bindings and an agreed bounded authentic corpus/capture, followed by the remaining M4 narrative workflow.

Validation for this implementation: 27 financial/evaluation unit checks, 58 existing query/retrieval/service/benchmark/usage/API regression checks, and five disposable Postgres lifecycle/research checks passed. Evaluation input integrity passed with unchanged historical golden/capture hashes. Dependency deprecation warnings do not affect these results.
