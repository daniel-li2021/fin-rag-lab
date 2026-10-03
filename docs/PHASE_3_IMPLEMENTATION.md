# Phase 3 implementation status

The October 3 [product review and next batch proposal](PRODUCT_NEXT_BATCH_PLAN.md) distinguishes this implementation from authentic release validation and prioritizes real company histories, evaluation and a demonstrable workspace.

Phase 3 now has an opt-in financial research workspace in the existing service, query graph, private API and local Streamlit app. It stores immutable owner-reviewed observations, pins source/version/build/hash identities once, checks required task coverage, and emits cited Decimal receipts or explicit gaps. Collections, saved answers, change indicators and separate reruns preserve research history. Ordinary `/query` behavior and the held experimental answer profile remain unchanged.

| Milestone | Implemented | Still required |
| --- | --- | --- |
| M1 | Immutable financial request/period/evidence/observation/coverage contracts; failure mapping, split design, historical identities and offline integrity checker | Populate and independently review the authentic development/holdout corpus; agree a paid paired-capture budget |
| M2 | Original span/cell/page validation, six support roles, normalized value/unit checks; exact period/scope/basis and cutoff selection; explicit fact revision/conflict selection; append-only version metadata corrections; owner-scoped immutable reviewed fact storage and reuse | Resolve actual fiscal boundaries and other authentic binding gaps; independently review promoted facts; expand report/revision corpus |
| M3 | Difference, growth, percentage-point change, profit margin and delivery/production ratio; precision-100 Decimal normalization, half-up display, both operand citations and formula | Authentic q08/q22 receipts remain blocked by unresolved bindings; additive YTD/Q4/TTM derivations remain deferred |
| M4 | Explicit plans of up to six tasks, three companies and three periods; finite natural-language lookup/comparison/ranking/trend templates; existing LangGraph research branch; complete-candidate ranking, partial answers and gaps; original passage search per company with at most two attempts and a shared 6,000-token ceiling | Broader natural-language intent; reviewed narrative synthesis and authentic q25/q26 correctness; authentic release evaluation. Lexical passage candidates are never treated as verified task coverage |
| M5 | Disabled; no planner calls | A sealed holdout and measured gain over M4 |
| M6 | Owner-scoped named collections/watchlists; immutable saved runs and JSON exports; byte/build/metadata and failed-refresh indicators; separate reruns with parent identity and result diff; local Streamlit coverage, periods, receipts, original passages and history | Full quality gates and an authentic measured release demo; broader change summaries and scheduled refresh remain deferred |

## Review authority

The private API is a single-owner trusted review surface. A submitted observation marked `reviewed` with a named `review_revision` is an **owner's manual semantic attestation** of metric, row/column, dates, scope and basis. The code independently checks original location, amount, unit and authorized source identity; it does not infer or certify those semantic associations. Do not submit model-written candidates as reviewed. Unreviewed or unresolved records cannot produce a numeric answer or calculation. These tests do not establish general extraction or narrative accuracy.

The six authentic [diagnostic cards](fixtures/phase3/authentic_observations.v1.json) preserve reviewed original locators but remain unverified. AMD and Tesla fiscal labels do not establish actual boundary dates; the Wells Fargo card also retains definition/basis/unit concerns. They yield **zero eligible authentic observations**. The three diagnostic questions are development-only; there are zero sealed holdout cases. The [evaluation contract](PHASE_3_EVALUATION.md) and [manifest](fixtures/phase3/manifest.json) freeze the design and historical inputs without inventing the planned 96 questions.

## Use

Apply the existing schema migration before using the new research or historical metadata-review routes:

```bash
python scripts/sources.py migrate
python scripts/check_phase3_evaluation.py
```

`POST /research` uses the existing bearer token and owner isolation. Supply `question` (a saved description), explicit `selections`, `tasks`, optional owner-reviewed `observations`, optional `calculations`, `mode` (`lookup`, `comparison`, `ranking`), `as_of` and `revision_policy`. Stored reviewed cards for pinned builds are reused automatically; conflicting immutable observation IDs reject. Matching cards are filtered in SQL by required company/metric/scope/basis/period before the 100-card ceiling. Unrelated library cards do not consume that bound; matching conflicts and revision predecessors remain eligible for validation. Narrow tasks or sources when matching cards exceed it. Every intended candidate and operand must be a task. The full schema is in [research.py](../src/financial/research.py), [models.py](../src/financial/models.py) and the authenticated API schema.

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

The returned JSON's `run_id` hashes its content, including source/review identities, inputs and derived receipts. `/research` returns an unsaved export; saved-run routes below retain immutable database history. Recalculation under changed code need not produce the same export. Keep pinned originals for independent replay; an archived source remains inaccessible to new research.

### Workspace routes

- `POST /research/observations` validates and stores one reviewed fact. Repeating identical input is safe; changing an existing ID rejects. `GET /sources/{source_id}/observations` lists current reviewed facts; an optional `version_id` selects a historical source version. Model-written candidates cannot certify their own semantics.
- `POST /research/questions` accepts a question plus `selections` or `collection_id`, and optional `save: true`. Finite templates have the form `show|compare|rank|growth|change|margin|delivery ratio|production gap GAAP|non-GAAP|operating consolidated|automotive|segment:<definition> <metric> for <confirmed companies> in Qn YYYY|FY YYYY [to Qn YYYY|FY YYYY]`. Example: `change GAAP consolidated gross margin for amd in Q4 2024 to Q4 2025`. Known `What was/is` lookup and `How did … change from … to …` phrasing preserve explicit dimensions. Margin/operating templates add both required operands; `period_policy: reporting_kind` explicitly allows unequal trend durations with receipt qualification. A missing dimension or ambiguous alias clarifies; unknown requested companies refuse without dropping them. Actual dates come from reviewed observations, never guessed fiscal labels. Unequal durations require explicit tasks and calculation policy.
- `POST /research/evidence` accepts company/query tasks and explicit selections. It searches retained original block text/rows, ignoring generated captions. One optional `repair_query` makes a second attempt. Each task gets a share of the 6,000-token ceiling and at most three whole-block candidates. Optional document-period filtering refers to confirmed source metadata, not fact-level reporting time; optional `as_of` requires known publication dates. No synthesis or arithmetic is authorized by lexical matches: results remain candidates with `binding_unverified` coverage and qualification. Exhaustion preserves the missing task and its reason.
- `POST /research/collections` creates or edits a named source selection; `GET` lists owner-scoped collections. A `watchlist` is a saved selection, without automatic fetching.
- `POST /research/runs` executes and stores a numeric run; `/research/evidence/runs` stores an evidence search. `GET /research/runs` lists history, and `GET /research/runs/{run_id}` reopens the immutable payload plus current source-change indicators. Opening history does not rerun the question. Question-template clarification/refusal outcomes are also saved with pinned inventory when `save=True`, and can be reopened or explicitly rerun.
- `POST /research/runs/{run_id}/rerun` creates a separate run over current versions of the same selected source IDs, with fresh stored cards and still-valid prior cards, a parent run ID and an answer/calculation diff. Required tasks, question, historical cutoff and scope/basis remain explicit; stale bindings cannot become current operands. A source archive blocks new research/reruns while preserving authorized owner access to saved history.

Saved executions add a unique execution ID/time before hashing so even an unchanged explicit rerun has its own history record. Changed bytes/builds/metadata flag potential staleness; this is not a semantic materiality claim. A failed refresh with unchanged active evidence reports the failure while retaining the saved answer and last-good corpus.

With `DATABASE_URL`, the default is **Research** in the existing local Streamlit app. Choose sources or a collection, inspect company/period/review inventory, choose numeric research or original passages, and run/save. The workspace shows gaps, formulas, cited operands, original candidates and export/history actions. **Library** reports current build page/child/card coverage separately from metadata review. **History** opens without re-executing and distinguishes evidence changes from result changes. Source edits and fact import are under **Owner administration**; fact import requires an explicit manual-review attestation. Clearing or opening another result clears the prior diff. This navigation does not implement public authorization. Streamlit remains a trusted local/SSH surface; use the bearer-authenticated API for network access. Small inventories use Markdown tables to avoid the installed native Arrow renderer crash observed during testing.

## Validation and release boundary

Focused synthetic checks exercise Decimal scale/precision, percentage-point direction, compatibility, missing/conflicting facts, cutoff behavior, complete rankings and reproducible output. Disposable real Postgres/API checks exercise snapshot reuse across source updates, historical builds, metadata correction history, bearer auth, owner/version isolation and archive rejection; existing lifecycle checks retain failed-refresh and restore coverage. The offline evaluation checker validates hashes, original locators and split leakage without model calls.

Integrity passing is not answer-quality promotion. Current-default improvement, authentic holdout accuracy, extraction quality, model cost/latency and planner gain remain `not_assessable`; release remains **held**. No new live-corpus ingestion, paid embedding/model/judge call, default promotion or cloud provisioning was performed; integration checks ingest synthetic data with offline embeddings. A full text scan of the original PDFs confirmed that AMD/Tesla do not state the required fiscal boundaries; their unrelated later-event/publication dates cannot supply those operands. Wells Fargo has printed period-end dates, but the existing CBL diagnostic's remaining definition/basis/unit concerns still prevent promotion. Next useful work is reviewed period/basis bindings and an agreed bounded authentic corpus/capture, followed by reviewed narrative synthesis.

Follow-up validation: 29 financial/workflow/evaluation unit checks, 58 existing query/retrieval/service/benchmark/usage/API regression checks, nine disposable Postgres lifecycle/research/workspace checks, and 34 additional core/chunking/metadata/source checks passed (130 unique checks). The workspace test runs a reviewed lookup and saves it through Streamlit. Checks cover separate reruns, reopened immutable answers, failed refreshes, both original company sources, owner isolation, archives and budget/cutoff behavior. Original-row reconstruction now preserves integer zero instead of turning it into an empty cell; this is checked on the evidence path. Evaluation input integrity passed with unchanged historical golden/capture hashes. Dependency deprecation warnings do not affect these results.
