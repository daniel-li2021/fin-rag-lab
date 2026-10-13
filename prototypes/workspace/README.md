# FinRAG visual prototypes

Two representative Next.js/React directions for visual review, isolated from the FastAPI/Streamlit product. No live generation, backend mutations, new auth/database or financial calculations. The design investigation, reference observations, evaluation and recommendation are in [Workspace design](../../docs/kb/WORKSPACE_DESIGN.md).

## Run locally

From the repository root:

```sh
.venv/bin/python prototypes/workspace/scripts/export-fixtures.py
cd prototypes/workspace
npm ci --cache /tmp/finrag-npm-cache
npm run check
npm run build
npm run preview
```

Open [comparison](http://127.0.0.1:3100/), [A — Folio](http://127.0.0.1:3100/?direction=folio) or [B — Meridian](http://127.0.0.1:3100/?direction=terminal). The static server binds only to loopback. `npm run dev` is optional; production build/preview avoids local filesystem watcher limits. No environment variables/API keys are required.

## Review interactions

- Research: select numeric cards, bars or citations; resize the always-visible Evidence Inspector by dragging the divider or focusing it and using arrow keys. Switch between exact excerpts, retained source pages and complete provenance.
- Library: search, filter issuer and inspect an actual cited source. It contains only the eleven original-byte identities used by the examples, not the full live corpus. Multiple registry instances of identical original bytes are represented once.
- History: search and page through ten saved executions; reopen a parent-linked rerun. The unsaved old-version query stays in the Hero walkthrough, not History.
- Heroes: all five preserved scenarios; toggle recast/as-reported, inspect withheld arithmetic/ranking, period-aware narrative, and original/rerun/old-version results.
- AMD collection: exact saved `+6.61%` calculation receipt, normalized operands, formula, full Decimal precision and fiscal intervals.
- Export: download the exact preserved result JSON. No new result is generated or saved.
- Narrow screens: use the Evidence button to switch between results and the inspector. Mobile deliberately uses a full-width inspector.

`public/fixtures.json` is a reproducible presentation bundle, not a new financial dataset. The exporter verifies the existing Hero hash envelope, copies result payloads unchanged, checks original PDF hashes and renders cited physical PDF pages. Full retained PDFs under ignored `public/originals/` require the local originals; they are not committed. The small original-page images, fixtures and fonts are retained for review. Self-hosted fonts carry their original OFL licenses. `npm run check` independently verifies exported payload equality, source hashes and key evidence boundaries.

Complete API integration, source selection for arbitrary new questions, persistent live owner history and full frontend implementation await visual approval. Any later live client must use the existing private FastAPI contracts and keep its bearer credential on the server.
