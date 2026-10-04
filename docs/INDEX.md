# Documentation index

Start with [STATE](STATE.md) for implemented behavior, evidence limits and next work. [NEXT_WORK](NEXT_WORK.md) is the only current plan. [CONTRIBUTING](../CONTRIBUTING.md) owns the update workflow and persistent integration mode; [AGENTS](../AGENTS.md) is the short agent entrypoint.

| Authoritative home | Purpose |
| --- | --- |
| [STATE](STATE.md) | Canonical current status and next action |
| [DECISIONS](DECISIONS.md) | Retained choices, negative results and supersession |
| [Next work](NEXT_WORK.md) — active development closure; release blocked on independent review/holdout custody | Integrated saved-narrative regression and source-change checks complete; pursue genuine unresolved discrepancies, demonstrate five Hero Scenarios, then close release/historical gates |
| [System KB](kb/SYSTEM.md) | Current architecture, source lifecycle, private API, research and saved history |
| [Runtime KB](kb/RUNTIME.md) | Local Postgres/UI, notebook compatibility, private Docker limits and restore |
| [Evidence and usage KB](kb/EVIDENCE.md) | Original provenance, structured outcomes and receipt semantics |
| [Evaluation KB](kb/EVALUATION.md) | Frozen labels, unchanged promotion gates and capture/replay recipes |
| [Financial policy](kb/FINANCIAL_POLICY.md) | Metric definitions, fiscal/revision comparability and review authority |

Code/contracts establish behavior; plans describe pending work; immutable captures establish only what was measured/reviewed in their pinned configuration. Verify disagreements, then update STATE. An implementation merge does not establish release quality or deployment.

## Evidence artifacts

- [Benchmark captures](benchmarks/): [integrated development closure](benchmarks/20261004-authentic-gaps/paired_summary.json), [new authentic gap review](benchmarks/20261004-authentic-gaps/gaps-corrected/reviewed_summary.json) and [real-byte source transition](benchmarks/20261004-authentic-gaps/source-change-corrected/result.json); original manifests, results, overlays, receipts, failed attempts and captured patches. Key records: [full development paired review](benchmarks/20261003-authentic-development/paired_summary.json), [current 48-case review](benchmarks/20261003-authentic-development/regression/reviewed_summary.json), [separate 16-case extension](benchmarks/20261003-authentic-development/extension/reviewed_summary.json), [narrative formatter candidate](benchmarks/20261003-authentic-development/presentation-candidate/reviewed_summary.json), [historical reviewed baseline](benchmarks/20261002-parent-bm25/reviewed_summary.json), [quote-bound paired result](benchmarks/20261002-financial-answers-bound/paired_summary.json), [original development capture](benchmarks/20261003-product-development/capture-v4/summary.json), [claim review](benchmarks/20261003-product-development/development_claim_review.v1.json), [usage/failure ledger](benchmarks/20261003-product-development/usage_ledger.v1.json), [historical control](benchmarks/20261003-product-regression/capture/summary.json).
- [Check artifacts](evidence/checks/): dated [contextual](evidence/checks/CONTEXTUAL_CHECK.json), [lexical](evidence/checks/LEXICAL_CHECK.json), [metadata](evidence/checks/METADATA_CHECK.json), [live smoke](evidence/checks/LIVE_CHECK.json) and [Docker](evidence/checks/DOCKER_CHECK.json) records.
- [Frozen fixtures](fixtures/) and [actual local screenshots](screenshots/). Ignored originals/caches/databases need separate acquisition/reproduction; receipts do not distribute them.

Keep only pending work in NEXT_WORK; consolidate/delete completed plans and overlapping prose. Git history retains historical wording. Multiple genuinely active workstreams can be rows in NEXT_WORK, with scope/status/dependencies; do not recreate a historical plan library.
