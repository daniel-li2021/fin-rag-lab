# Evaluation and reproducibility

This is the canonical evaluation contract, including unchanged `phase3-design-v1` release thresholds. [STATE](../STATE.md) owns current evidence/readiness; [NEXT_WORK](../NEXT_WORK.md) owns pending validation. Captured configurations, outputs, raw token usage, overlays and failures remain in [benchmarks](../benchmarks/) and [checks](../evidence/checks/); redundant Markdown summaries are not retained.

## Labels and splits

The historical [golden set](../../data/golden_set/golden.jsonl) and [labels](../../data/golden_set/labels.v1.json) remain unchanged and hash-bound to the original PDFs. Labels carry q01–q30, expected outcomes, original spans, numeric units/tolerances, company/period/scope and rubric; generated text and transient chunks cannot supply gold evidence. Corrected labels explicitly distinguish q18 automotive/consolidated scope, q23 common-period/revenue definition and q24 margin basis, Gaming versus combined Client/Gaming, and qualitative AI activity versus a shared numeric AI-revenue metric.

The product contract requires 96 cases across six primary slices, each with eight development and eight holdout cases: multi-document coverage, temporal/scope, calculations/units, clarification, conflicts/revisions, missing evidence. Every question has exactly one primary slice and optional cross-tags; at least 20 authentic holdout cases must carry `numeric` or `calculated`. A release question needs frozen expected outcome, source hashes/locators, observation IDs, period/basis/scope, operands/result/tolerance when applicable, gap list and semantic rubric before answers are inspected.

Split whole report families, company-period keys and revision lineages together. A multi-document case binds every included family. A report or amendment used in development cannot appear in holdout, including through another question ID or near-duplicate table. The legacy three reports/retained questions and all product development sources/cases have informed implementation and are development-only. Synthetic adversarial cases are separate unit evidence and never enter authentic release denominators. Holdout use for tuning invalidates that holdout; create a new sealed revision before further promotion claims.


The product contract additionally requires eight narrative and eight answerable cross-company cases per split, **7/8 strict** in each subgroup, and at least 12 answerable holdout cases needing two distinct report families. Repeated companion values are not independent multi-document success. Independent second review of release-critical facts/calculations/revision mappings is required; disclose actual reviewer identities/coverage.

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

Freeze corpus, labels, model, source/version policy, original-evidence budget, cache mode, review policy and paid budget before any capture. Compare one variable at a time and publish paired wins/losses and all denominators. Do not run paid tests in CI. A budget freeze is not authorization for a model capture; each paid capture needs its own authorized bounded scope.


## Retrieval promotion gate

Before promoting contextual retrieval: +0.10 absolute macro evidence recall within the same 2,400-token original-evidence budget; two additional correct factual numeric answers, with no formerly correct answer lost; no new wrong-period/scope assertions; all four out-of-corpus questions handled correctly; no invalid citations; mean faithfulness regression ≤0.02; online p95 latency and mean query cost increase ≤20%. Preapprove an ingestion/context budget. Report paired question deltas and uncertainty. Undefined numeric/citation review or unknown costs cannot pass the gate. Retain parent-child when results are inconclusive. Thirty questions are a screening set, not statistical proof.


Two additional numeric successes are impossible against a 9/10 baseline on ten questions. Keep that experiment held; changing its gate requires an explicitly approved larger paired design, never a retroactive relaxation.

## Scoring and capture semantics

Evidence recall counts each required span once, requires the original source hash and page plus the normalized original quote, and treats legacy/unresolved provenance as a miss. Recall@20, final recall, complete evidence and MRR use supported-question denominators. Quote-level matching is deliberately conservative: extractor formatting differences can cause misses and require reviewed span mappings, never relaxed source identity. Numeric accuracy requires reviewed `numeric_claims` with matching entity, period, scope and normalized unit; missing review is undefined, not a fabricated success. Arbitrary prose numbers do not demonstrate correctness. Citation validity requires the cited chunk/document/version and original spans to match a retrieved context; a `resolved` flag alone is insufficient. Citation support still requires claim review. Empty/incomplete verification cannot establish a correct refusal, and missing reasoning usage remains unknown. Semantic answers require rubric review. Ragas metrics, when supplied, are secondary; answer relevancy/context precision/recall are undefined for refusal/clarification cases. Every mean reports its denominator; empty denominators are null.


`run_benchmark.py` saves an append-flushed result stream, manifest and summary in a new directory; partial failures survive and existing outputs are not overwritten. Manifests pin labels/corpus/code/config, original evidence revision, index/vector artifacts, embedding profile, reasoning configuration, dependencies and prices. `--verify` is optional claim checking; `--ragas` is separately budgeted judging with separate `evaluation_usage`, never hidden inside online query cost. Unknown usage stays unknown; report metric/cost/latency denominators and linearly interpolated p50/p95.

Captures reject legacy provenance and runtime/build embedding mismatch; rebuilding is explicit. Default Ask uses quick/deep 3/8 parents, distinct from the controlled 2,400-original-token retrieval screen. A–D contextual and SQL lexical comparisons reuse matched child boundaries/vectors/filters/fusion/budget. The [portable scoring fixture](../../data/golden_set/retrieval_screen.v1.json) replays scores, not retrieval/token selection; full contexts remain in the ignored original experiment directory.

The legacy [Phase 3 manifest](../fixtures/phase3/manifest.json) is an immutable three-question diagnostic, not the newer 168-card/48-case product corpus or populated holdout. Its checker can pass integrity while reporting release held/unassessable. [Product labels](../fixtures/product/development_cases.v1.json) are separately frozen before generation; the development runner never opens holdout.

## Commands from repository root

```sh
# Offline replay/integrity only; no database or model calls.
python scripts/check_phase3_evaluation.py
python scripts/replay_answer_review.py docs/benchmarks/20261002-parent-bm25
python scripts/run_benchmark.py --replay docs/benchmarks/20261002-parent-bm25/results.jsonl
python scripts/run_product_development.py --pricing docs/benchmarks/20261003-product-regression/pricing.json --output-dir /tmp/finrag-label-check

# New paid work only under a declared authorized budget; never rebuilds implicitly.
REASONING_EFFORT=none python scripts/run_benchmark.py --backend postgres --owner experiment \
  --limit 0 --pricing docs/benchmarks/20261002-parent-bm25/pricing.json --output-dir /tmp/finrag-NEW
```

Positive `--supplement-k 1..8` opts into the held quote/calculation protocol; default is zero. `--ids` selects known qIDs; Postgres `--reuse-query-embeddings` uses the exact model/input-hash cache and records fresh usage on misses. Product development requires explicit `--capture`, a new output directory, frozen price/config and live authorized source/build/hash checks before paid calls; labels-only is the default. No paid capture runs in CI. Use `python -m pytest` for targeted tests.
