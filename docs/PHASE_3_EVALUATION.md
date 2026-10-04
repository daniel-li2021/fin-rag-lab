# Phase 3 evaluation contract (M1)

Frozen design revision: `phase3-design-v1`, October 3, 2026. This is the retained evaluation contract; the obsolete design proposal is consolidated into [decisions](DECISIONS.md) and the [remaining release plan](plans/RELEASE_VALIDATION.md). The offline [manifest](fixtures/phase3/manifest.json) pins immutable inputs and the original development diagnostics. Run `python3 scripts/check_phase3_evaluation.py` without credentials, ingestion, embeddings or model calls. Its diagnostic counts do not describe the later product corpus; [STATE](STATE.md) owns current implementation and evidence status. The gates below are unchanged.

## Splits and authority

Keep the existing 30 questions and labels unchanged. The 96 new questions require six primary slices, each with eight development and eight holdout cases: multi-document coverage, temporal/scope, calculations/units, clarification, conflicts/revisions, missing evidence. Every question has exactly one primary slice and optional cross-tags; at least 20 authentic holdout cases must carry `numeric` or `calculated`. A release question needs frozen expected outcome, source hashes/locators, observation IDs, period/basis/scope, operands/result/tolerance when applicable, gap list and semantic rubric before answers are inspected.

Split whole report families, company-period keys and revision lineages together. A multi-document case binds every included family. A report or amendment used in development cannot appear in holdout, including through another question ID or near-duplicate table. The current three reports and retained questions have already informed implementation and are development-only. Synthetic adversarial cases are separate unit evidence and never enter authentic release denominators. Holdout use for tuning invalidates that holdout; create a new sealed revision before further promotion claims.

The sidecar contains a small Codex-reviewed diagnostic fact set with exact original spans, parser-cache review and original-page visual review. This is manual binding, not independent human judging or general extraction precision. AMD fiscal labels do not establish exact fiscal calendar dates; calendar boundaries must remain unresolved rather than assuming December 31. Wells Fargo's segment transfer disclosure prevents treating changed segment membership as automatically comparable. Original raw PDF hashes and build/version pins remain authoritative; generated captions and model answers are excluded from binding evidence.

## Defect-to-contract map

| Retained failure | Defect | Required contract and offline check |
| --- | --- | --- |
| q07, q15, q16 | Missing Gaming/ramp/outlook passages; complete recall can still refuse | Per-task original evidence requirements; missing and supported-but-unusable outcomes remain distinct |
| q08 | Correct annual amount cited a title/caution card | Value, row, period, unit, basis and scope links; operand citation must point to the amount's original evidence |
| q18, q23, q24 | Period, basis and common metric unresolved | Clarify unresolved request dimensions before selecting facts; never silently pick a company/period |
| q21 | Segment ranking may omit a segment | Required-cell coverage; any missing or incompatible segment blocks full ranking |
| q22 | Wrong operands/direction despite retrieved values | Separate Q4 2024 51% and Q4 2025 54% bindings; deterministic +3 percentage points |
| q14, bound q13, final-default q11 | Post-quarter events and wrong-period trends | Fact-level fiscal labels/boundaries and event dates; no quarter/YTD/annual substitution |
| q25 | AI activity is not a common numeric AI-revenue metric | Preserve qualitative supported evidence and explicit non-comparability |
| q26 | Only one company's risk evidence survives | One task per company, complete risk-source coverage before synthesis |
| Bound q02/q03/q10 | Sparse table rows lose labels/columns | Separate original support roles, manual reviewed binding when extraction is uncertain; generated/model-declared labels cannot certify a fact |
| Remaining false refusals | Location checks reject usable evidence or coverage overstates usability | Score false refusal, strict correctness and observation binding separately; safety abstention counts against usable-answer accuracy |

## Frozen gates

Historical regression: preserve all 19 prior strict successes; reach at least 24/30 strict, retain at least 9/10 numeric with no formerly correct numeric loss, 3/3 clarification, 4/4 out-of-corpus refusal and 4/4 strict cross-document (including two clarification cases). A fresh full 30-question current-default paired baseline is required; the selected 12 cannot replace it.

Authentic holdout: at least 41/48 strict, at least 7/8 per primary slice, at least 95% numeric accuracy over a frozen denominator of at least 20, at least 90% complete required evidence on answerable tasks, and 100% operand coverage for calculations issued. Every numerical fact issued requires a verified binding. Missing/clarification/conflict cases are scored on correct outcome and precise gaps, not nonexistent evidence recall.

Safety: zero unsupported financial assertions, wrong-period/scope substitutions, invalid citations, absent operand citations, unauthorized-source use or full rankings with missing/non-comparable cells. Every critical missing/conflict/revision case must choose its labeled safe outcome. A success elsewhere never compensates for a safety failure.

Matched simple-path receipt mean cost and service p95 may rise at most 20%; ordinary supported lookups have zero planner calls. Initial complex-path allowance is at most 1.5 times deterministic M4 mean receipt cost and p95 on matched questions, with one planner, six tasks, two retrieval attempts per task and 6,000 original tokens. M5 requires at least three extra strict holdout successes and no previously correct loss. Missing cost/usage receipts mean `not_assessable`, not zero. Existing retrieval promotion gates remain unchanged.

Freeze corpus, labels, model, source/version policy, original-evidence budget, cache mode, review policy and paid budget before any capture. Compare one variable at a time and publish paired wins/losses and all denominators. Do not run paid tests in CI. A budget freeze is not authorization for a model capture; no paid recapture was authorized for this implementation.

## Diagnostic-fixture scope and release decision

The original manifest remains a three-family diagnostic fixture, with zero eligible observations and no sealed holdout cases. Its checker reports `held` and `not_assessable` for release metrics; it does not evaluate the newer 22-source/168-card development corpus. That development extension and its 48-case captures are recorded in [STATE](STATE.md) and [development results](PRODUCT_DEVELOPMENT_CAPTURE.md). Independent release-critical review, disjoint sealed labels and matched historical/holdout gates remain required through the [release plan](plans/RELEASE_VALIDATION.md). No default answer path or historical golden label is promoted by these artifacts.
