# Frozen authentic development captures — October 3

All four full captures use the same pre-generation 48-question development label hash, 22-source development inventory/window/build manifest and named original fact review. The separate 48-question holdout was not accessed. All generated claims retain unreviewed status in their immutable captured/saved results.

| Capture | Mechanical checks | Numeric bindings | Generator calls | Base configured estimate | Main finding |
|---|---:|---:|---:|---:|---|
| `capture` | 46/48 | 25/25 | 8 | $0.0025334 | Two safe false refusals; exact-copy rejection details were incomplete |
| `capture-v2` | 48/48 | 25/25 | 8 | $0.0025501 | Post-capture original review found a wrong metric section despite valid quote provenance |
| `capture-v3` | 47/48 | 25/25 | 8 | $0.0030550 | Correct section context; one invented long excerpt ID refused safely |
| `capture-v4` | 48/48 | 25/25 | 8 | $0.0024188 | Short excerpt IDs and original section order; development claim/context review completed |

The latest capture has eight mechanical successes in each of six slices and 48/48 exact saved-history reopens. Eight narrative requests (six supported, two unsupported) used **20,488 input / 740 output tokens**; no planner, embeddings, VLM or paid semantic judge was called. Mixed total p50 **0.0112s** / p95 **1.8075s** is dominated by deterministic numeric/clarification/refusal requests; narrative-only denominators and latency are in [usage ledger](usage_ledger.v1.json).

The [Codex post-capture review](development_claim_review.v1.json) preserves exact original claim locators, necessary split-paragraph/metric context and the failure ledger. It covers 12 generated claims plus two supported refusals. It is development review, not independent human release review. Strict authentic accuracy and the independent semantic-support metric remain **undefined**; the predeclared matched historical and sealed holdout gates have not passed.

The ledger includes authentic ingestion, the separate historical 30-question control, all four development captures and one live Streamlit narrative rerun: reported usage with configured base input/output estimates totals **$0.05852726**. Raw cache/token details remain linked, cache tariffs are not adjusted, and this is not a billing invoice. A separate pre-fix HTTP 400 runtime attempt returned no usage/cost receipt and stays unknown. Captures are immutable; subsequent UI history/dotenv/diff fixes are verified independently and do not relabel these recorded code hashes.
