# Contribution workflow

**Current integration mode: AUTO**

This line is the persistent mode for future tasks. Change it when the user switches modes; the latest explicit user instruction takes precedence.

| Mode | Integration behavior |
| --- | --- |
| `AUTO` | Validated, in-scope work may merge automatically. Complete required checks and verify the resulting remote main ref. |
| `REVIEW` | Prepare and validate the change, commit/push it and present the diff/PR; stop before merge for the owner's review. |

## One workflow

1. Start at [INDEX](docs/INDEX.md) and [STATE](docs/STATE.md); verify the checkout and current code/receipts. Read only the relevant plan, contracts and KB. Keep unrelated local changes out of the change.
2. Implement the smallest complete change. Reuse valid cached outputs and immutable captures. Run focused validation appropriate to the change; paid captures, new ingestion and deployment require their own task scope and bounded allowance.
3. **Update documentation after implementation, before integration, in the same change.** Update the affected contract/KB where behavior changed, STATE's implemented status/evidence/next action, and any affected active plan's status/remaining work. Update INDEX when plans/docs move or status changes; update README when setup or the product introduction changes; update AGENTS only when agent guidance changes. Record durable choices/supersession in [DECISIONS](docs/DECISIONS.md). Keep CONTRIBUTING's persistent mode current. Do not create a parallel progress or handoff document.
4. Validate the diff and `python scripts/check_docs.py`. For evidence changes, replay the relevant saved results/integrity checker; record configuration, denominators and limitations in the owning result report. Documentation-only changes need no corpus rebuild, model call, full test suite or application build.
5. Commit/push only the scoped files. Integrate according to the current mode, respecting required checks; in AUTO, merge validated work and verify remote main contains it. Do not monitor CI after push by default unless required for merge, explicitly requested or a failure is known. Finish with the result, validation and any material remaining limitation.

## Documentation ownership

| File/home | Responsibility |
| --- | --- |
| [README](README.md) | Runnable introduction and link to INDEX |
| [AGENTS](AGENTS.md) | Minimal agent start and work guidance |
| [STATE](docs/STATE.md) | One current status, validation boundary and next-work path |
| [INDEX](docs/INDEX.md) | Navigation and every active plan's status/purpose/next action |
| `docs/plans/` | Only current scoped plans; multiple plans allowed with explicit dependencies |
| [DECISIONS](docs/DECISIONS.md) / `docs/kb/` / contracts | Durable rationale, supersession and reusable technical knowledge |
| Result reports, `docs/benchmarks/`, `docs/fixtures/`, screenshots | Dated measured/reviewed evidence and reproducibility inputs |

When closing an old plan/review/investigation/checkpoint/handoff/progress document, extract its durable content into the appropriate home, fix references and **delete the obsolete file**. Preserve the original only when its exact bytes are needed for reproducibility or immutable evidence. Git history already retains old coordination prose. Frozen benchmark inputs/results/review overlays/patches/receipts stay immutable and at their referenced paths; later captures use new directories and corrections use explicit overlays.

## Cheap validation

```sh
python scripts/check_docs.py
# Frozen legacy Phase 3 diagnostic integrity; not expanded-corpus accuracy.
python scripts/check_phase3_evaluation.py
# Saved historical review/receipt replay; no model calls or database.
python scripts/replay_answer_review.py docs/benchmarks/20261002-parent-bm25
```

For code changes use `python -m pytest` with relevant existing checks. CI currently runs `tests/unit` with lab and persistence dependencies; it does not run paid capture or certify authentic release accuracy. [Benchmark](docs/BENCHMARK.md) and [evaluation](docs/PHASE_3_EVALUATION.md) own release/promotion gates.
