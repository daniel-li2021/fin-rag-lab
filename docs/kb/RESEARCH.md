# Research contracts and routes

Current readiness is in [STATE](../STATE.md); [metric policy](../PRODUCT_METRIC_POLICY.md) owns semantic review and comparison definitions. The existing private service, query graph, API and local Streamlit use immutable owner-reviewed observations, pinned source/version/build/hash identities, explicit coverage/gaps and cited Decimal calculations. Direct Ask retains a separate execution path.

## Review and evidence authority

A submitted `reviewed` observation with a named `review_revision` is a manual semantic attestation of metric, row/column, dates, scope and basis. Code validates authorized originals, location, amount and units; it does not certify semantic meaning. Unreviewed/unresolved observations cannot authorize numeric answers. The 168 development cards carry named Codex review; independent release review is still required.

Original passage search returns `binding_unverified` candidates by default. Optional **Draft a cited narrative** makes at most one generator call (60-second timeout, no retries, 1,600 output tokens), requiring exact unique original quotes, offered excerpt IDs and complete task coverage. Unknown IDs/numbers reject. Provenance bounds do not establish semantic support; generated claims remain unreviewed even after a separate post-capture review overlay. [Draft contract and captures](../PRODUCT_DEVELOPMENT_CAPTURE.md).

## Use

Apply the existing schema migration before using the new research or historical metadata-review routes:

```bash
python scripts/sources.py migrate
python scripts/check_phase3_evaluation.py
```

`POST /research` uses the existing bearer token and owner isolation. Supply `question` (a saved description), explicit `selections`, `tasks`, optional owner-reviewed `observations`, optional `calculations`, `mode` (`lookup`, `comparison`, `ranking`), `as_of` and `revision_policy`. Stored reviewed cards for pinned builds are reused automatically; conflicting immutable observation IDs reject. Matching cards are filtered in SQL by required company/metric/scope/basis/period before the 100-card ceiling. Unrelated library cards do not consume that bound; matching conflicts and revision predecessors remain eligible for validation. Narrow tasks or sources when matching cards exceed it. Every intended candidate and operand must be a task. The full schema is in [research.py](../../src/financial/research.py), [models.py](../../src/financial/models.py) and the authenticated API schema.

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
- `POST /research/evidence` accepts company/query tasks and explicit selections. It searches retained original block text/rows, ignoring generated captions. One optional `repair_query` makes a second attempt. Each task gets a share of the 6,000-token ceiling and at most three whole-block candidates. Optional document-period filtering refers to confirmed source metadata, not fact-level reporting time; optional `as_of` requires known publication dates. Lexical matches alone authorize neither synthesis claims nor arithmetic: results remain candidates with `binding_unverified` coverage and qualification. Exhaustion preserves the missing task and its reason.
- `POST /research/collections` creates or edits a named source selection; `GET` lists owner-scoped collections. A `watchlist` is a saved selection, without automatic fetching.
- `POST /research/runs` executes and stores a numeric run; `/research/evidence/runs` stores an evidence search. `GET /research/runs` lists history, and `GET /research/runs/{run_id}` reopens the immutable payload plus current source-change indicators. Opening history does not rerun the question. Question-template clarification/refusal outcomes are also saved with pinned inventory when `save=True`, and can be reopened or explicitly rerun.
- `POST /research/runs/{run_id}/rerun` creates a separate run over current versions of the same selected source IDs, with fresh stored cards and still-valid prior cards, a parent run ID and an answer/calculation diff. Required tasks, question, historical cutoff and scope/basis remain explicit; stale bindings cannot become current operands. A source archive blocks new research/reruns while preserving authorized owner access to saved history.

Saved executions add a unique execution ID/time before hashing so even an unchanged explicit rerun has its own history record. Changed bytes/builds/metadata flag potential staleness; this is not a semantic materiality claim. A failed refresh with unchanged active evidence reports the failure while retaining the saved answer and last-good corpus.

With `DATABASE_URL`, the default is **Research** in the existing local Streamlit app. Choose sources or a collection, inspect company/period/review inventory, choose numeric research or original passages, and run/save. The workspace shows gaps, formulas, cited operands, original candidates and export/history actions. **Library** reports current build page/child/card coverage separately from metadata review. **History** opens without re-executing and distinguishes evidence changes from result changes. Source edits and fact import are under **Owner administration**; fact import requires an explicit manual-review attestation. Clearing or opening another result clears the prior diff. This navigation does not implement public authorization. Streamlit remains a trusted local/SSH surface; use the bearer-authenticated API for network access. Small inventories use Markdown tables to avoid the installed native Arrow renderer crash observed during testing.
