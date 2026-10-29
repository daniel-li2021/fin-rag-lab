# Financial research workspace design

The owner selected **Meridian** on October 14, superseding the original Folio recommendation and visual-review pause. The real Next.js/React application in `frontend/` uses the existing FastAPI contracts; Streamlit remains private administration. The October 13 investigation and two read-only [prototypes](../../prototypes/workspace/README.md) below retain the original design rationale. [STATE](../STATE.md) owns current deployment/validation status; [NEXT_WORK](../NEXT_WORK.md) owns remaining work.

## Workspace guidance and recovery

The October 28 local update applies the ClaimFlow post-draft process to Meridian: reproduce concrete journey failures, add guidance at the point of use, recover without silently replaying work, and check desktop/mobile interactions against the existing evidence boundary. The midnight workbench, backend authority and eleven frozen payloads remain intact. This is an implementation check, not a human usability study or full accessibility certification.

- **Entry:** Demo uses **Explore research** and a five-story starter list. A collapsible **How to use this workspace** guide explains story → cited evidence → immutable History. Live mode keeps **New research** and its existing private composer.
- **Fresh starts and navigation:** Starting research clears the old answer, selection, comparison and source inspector. Back/Forward reopens the URL's saved run; an aborted older URL read cannot replace a later view. Opening a deep link has an explicit loading state.
- **Walkthroughs:** Multi-step stories retain direct step selection and add bounded Previous/Next controls with an announced step count. These controls only select preserved results; they do not execute reruns.
- **Recovery:** Library/History empty searches offer one-action clearing. Archive failures offer **Retry archive**; History failures show **Retry history** rather than a misleading empty result. Other failed reads retry their original read. Network/unreadable errors retain the current view/draft; uncertain mutation responses direct the owner to History before another submission. No automatic mutation retry or new idempotency guarantee is introduced.
- **Evidence access:** On mobile, opening evidence focuses the return control; Escape or Return restores the invoking citation/button. Source inspection uses the same return behavior. The footer control exposes expanded state and is disabled when there is no result or inspected source. Textareas inherit typography and visible keyboard focus.

The dependency patch pins Next.js 16.4.1, following the upstream [image optimization](https://github.com/advisories/GHSA-2464-fhr4-w9xw) and [cache function](https://github.com/advisories/GHSA-673q-mjm6-r5xr) advisories. The local production audit reports zero vulnerabilities after installation. This says nothing about whether the previously hosted build has been patched.

### Bounded journey review

| Step | Captured finding and final behavior | Evidence |
| --- | --- | --- |
| 1. Start/explore | Initial comparison preserved; a fresh exploration now clears the previously reopened answer and exposes the five stories and usage guide. Healthy in the checked local flow. | [Initial screen](../screenshots/meridian-ux-20261028/01-before-research.png), [reproduced stale-answer bug](../screenshots/meridian-ux-20261028/02-before-new-research.png), [updated exploration](../screenshots/meridian-ux-20261028/06-explore-research.png) |
| 2. Follow a story | Previous/Next controls and step counts work on desktop/mobile, preserving original/rerun/old-version identities. Healthy in the checked local flow. | [Guided steps](../screenshots/meridian-ux-20261028/03-guided-steps.png) |
| 3. Inspect evidence | Citation switching, excerpts, provenance and mobile return focus pass; saved financial values and full source bindings remain unchanged. Healthy in the checked local flow. | [Updated comparison and evidence](../screenshots/meridian-ux-20261028/07-research-evidence.png) |
| 4. Recover/reopen | Controlled local 503s recover through archive/History retries; a five-second delayed saved-run response cannot override navigation. Healthy for these bounded failures. | [Archive failure](../screenshots/meridian-ux-20261028/04-archive-recovery.png), [History failure](../screenshots/meridian-ux-20261028/05-history-recovery.png) |

The [dated receipt](../evidence/checks/FRONTEND_UX_20261028.json) records exact checks and limits. Screenshots establish visible layout, not contrast compliance, screen-reader behavior or physical mobile keyboard behavior. No paid generation, database mutation, backend/cloud activation, public deployment or financial accuracy re-evaluation is part of this update. Historical design conclusions below describe the October 13 prototype stage, not the current frontend's implementation status.

## Investigation and access boundary

Inspected current private API, research/result, original-binding, Decimal receipt and immutable history contracts; reused the hash-bound Hero captures and existing `dev-09` calculation. Product investigation used public product pages, actual published interface images, a live shadcn block and primary documentation. No paid/logged-in competitor workspace, account creation, provider generation or paid template purchase occurred. Typography observations describe the rendered visual treatment, not verified proprietary font-family names. Competitor history interactions below are documented/publicly demonstrated patterns, not a personally tested authenticated session.

### Fiscal.ai / FinChat

The [Terminal page](https://fiscal.ai/products/terminal/) publishes a [statement workspace image](https://a.storyblok.com/f/107812/2696x1288/f640959ebf/terminal-mockup-wide.jpg): dark shell, small navigation rail, company context at top, horizontal research tabs, controls above a wide multi-period financial statement, right-aligned numeric columns and restrained green accents. The source filing appears beside the statement in a contrasting light document treatment. A second page illustration places a chart above statement rows. The product explicitly supports click-through source auditability.

Apply: keep fiscal intervals and definitions in the result; make the amount itself selectable; place an original beside structured data. Avoid: market-price hero cards, sprawling terminal tabs, financial ratios unsupported by the saved request, or decorative charts. FinRAG's result must remain about the actual research question.

### Elicit

Inspected [Elicit's published research interfaces](https://elicit.com/), including the screening quote and Library images. Screening is a two-column evidence table: source identity on the left, structured answer on the right, with compact concept markers and an adjacent supporting-quote card. Quiet borders, small sans text, ample white space and muted teal keep attention on the evidence. Library uses collection navigation on the left, source rows centrally, search above the rows and tags alongside them. Its [table/figure extraction guidance](https://support.elicit.com/en/articles/14758168-extracting-data-from-a-table-or-figure-within-a-paper-in-column-answers) makes original table support inspectable.

Apply: inspect one bound fact or claim without losing the answer; distinguish source identity from extracted interpretation; reuse originals through Library. Replace ephemeral quote popovers with a persistent inspector because financial row/period/unit/basis bindings often span several excerpts. Do not give retrieved candidates the visual status of claim citations.

### Quartr Pro

The [Pro product page](https://quartr.com/products/quartr-pro) shows source cards attached to claims, with source-person/company/event context, and a transcript view with a narrow document/event hierarchy. Source previews are neutral, compact and legible; branding is quieter inside the product than on the marketing page. Published examples also show structured AI output tables and export menus. [Slide history documentation](https://quartr.com/features/slide-history-comparison) describes selecting a slide to reveal historical versions below it, aligned in sequence without leaving the document viewer.

Apply: exact period labels beside each narrative claim; source context close to the claim; before/after evidence in one research flow. FinRAG adapts the history idea to its own immutable run and explicit parent-linked rerun contract. No transcript/audio/events/automation features are added.

### OpenBB Workspace

Inspected the [published Workspace interface](https://openbb.co/products/workspace/): horizontal workspace tabs above a dense grid, compact widget headers, charts and numeric tables in the main area, separate AI/source-analysis pane on the right. The image combines a market chart with key metrics and repeated analysis tables; the AI pane is a supporting tool rather than the whole screen. Light neutral surfaces and thin separators make dense material readable.

Apply: distinct result and inspection zones, independently scrollable content, compact structured comparisons. Avoid: movable widget dashboards, connectors, entitlements or Copilot infrastructure. The site currently also carries a stewardship/wind-down notice; it is a visual reference, not a dependency or hosting recommendation.

### Open-source implementation references

- [shadcn/ui Blocks](https://ui.shadcn.com/blocks) and the [actual dashboard-01 preview](https://ui.shadcn.com/view/new-york-v4/dashboard-01): useful sidebar composition, aligned action bars, tables and responsive shell. The default KPI-card/dashboard hierarchy leads with unrelated aggregate metrics; FinRAG instead leads with a research question and a structured result. The [Resizable primitive](https://ui.shadcn.com/docs/components/base/resizable) supplies accessible keyboard/pointer resizing through `react-resizable-panels`, used directly here. No whole template was imported.
- [Tremor](https://www.tremor.so/): useful compact bar lists, stable number/unit hierarchy, subdued grids and filter patterns. Its open components and premium Blocks are distinct offerings; no paid block was used. Two or three preserved values only need a zero-baseline bar list, not a chart suite, time-series interpolation or synthetic market feed.
- [Vercel Chatbot](https://github.com/vercel/chatbot), its [entry demo](https://chatbot.ai-sdk.dev/) and [Artifacts documentation](https://chatbot.ai-sdk.dev/docs/customization/artifacts): useful separation of conversation and persistent work surface, plus version/diff interaction. Its chat-first greeting and general generation stack do not fit FinRAG's primary identity. No AI SDK, provider gateway, new chat store or resumable streams were adopted.
- [Wealthfolio](https://wealthfolio.app/): visually inspected desktop/mobile investment previews. Calm surface treatment, slim navigation, restrained charts and exact right-aligned account values are useful references. Portfolio balance, account aggregation and trading features have no place in this research prototype. [Ghostfolio](https://github.com/ghostfolio/ghostfolio) was reviewed as a secondary open-source reference for financial navigation, chart/time-window controls and mobile-first constraints; no live authenticated session or source reuse. Its Angular/AGPL implementation is not a Next.js starter.
- [Next.js finance-dashboard](https://github.com/shubham-srv/finance-dashboard): reviewed repository structure and documented analytics/table components. It expressly uses hardcoded demo chart data and mock authentication. It is a useful comparison for implementation organization, but not a foundation for evidence authority, financial demonstrations or private API access. No code was copied.

## Two cohesive directions

**A — Folio: editorial research desk.** Warm paper `#f5f4ef`, near-white original surfaces, deep green navigation `#19382d`, green selected evidence and amber qualification. Libre Caslon Display gives the note title an editorial identity; DM Sans handles controls and body; IBM Plex Mono handles identity/precision details. The left navigation keeps Research, Library, History and Heroes stable. A generous question panel leads into financial values, the exact fact table, a supporting bar list and coverage. The right evidence margin stays visible and resizable. Narrative cards read as dated research paragraphs. Library is a restrained report catalog; History is a readable research record. [Research screenshot](../screenshots/workspace-design-20261013/folio-research.jpg), [narrative](../screenshots/workspace-design-20261013/folio-narrative.jpg), [source change](../screenshots/workspace-design-20261013/folio-source-change.jpg).

**B — Meridian: analyst workbench.** Midnight slate `#101722`, raised panels `#151f2e`, thin blue-gray rules, cool blue selection and muted issuer colors. Sans headings and monospaced amounts emphasize comparison. Main navigation moves into the top bar; the left area is a compact collection/scenario index. Question and value cards are shorter, the bar comparison appears before the exact table, and very wide screens place chart/table side by side. Coverage, full fiscal intervals, source pages and immutable history are identical in authority and content. [Research screenshot](../screenshots/workspace-design-20261013/meridian-research.jpg), [History](../screenshots/workspace-design-20261013/meridian-history.jpg).

Both use semantic buttons, visible focus, keyboard resizing, reduced-motion support and native table/summary controls. At narrow widths, the persistent inspector becomes an explicit full-width evidence view with return navigation; simultaneous tiny columns would impair source reading. Fonts are served locally with OFL licenses. Nothing is selected by color alone.

## Comparison and recommendation

This is a hands-on design/engineering evaluation, not a measured user study or a claim of validated accessibility compliance.

- **Usability:** Folio makes the research question, period-specific reading and adjacent original easy to follow. Meridian shortens scanning paths for numeric comparisons. Both allow one-action metric/bar/citation inspection and preserve the inspector across navigation. A raw JSON export and full provenance are secondary disclosures.
- **Visual quality:** Folio has the more distinctive portfolio identity and feels like a serious research product. Meridian is cohesive and familiar to an analyst, but its dark terminal treatment is less differentiated. Published reference patterns informed the layouts; no competitor interface was cloned.
- **Density:** At the tested 1440×1000 desktop breakpoint, Folio shows question, two values and their full fact table before its supporting chart; Meridian brings the chart and table into the first screen, with coverage beginning at its lower edge. On tablet, long titles and factual rows wrap/scroll while the inspector retains useful width. Neither compresses the original into an unreadable inline preview.
- **Complexity:** Both are one small Next.js app with a shared result/evidence renderer, CSS direction rules and five runtime dependencies (Next, React, React DOM, Lucide, panel resizing). No chart framework, auth service or backend change. Meridian requires more density/breakpoint tuning; Folio spends more vertical space. Supporting two permanent production directions would duplicate design maintenance, so approval should select one.

Recommend **Folio** as the product identity: FinRAG's advantage is inspectable research, exact calculations, useful gaps and trustworthy history. Its editorial reading rhythm makes those strengths visible. The clear cost is longer numeric pages. Meridian is preferable if the owner prioritizes repeated numeric scanning and maximum first-screen density. No hybrid or complete frontend was implemented after this recommendation.

## Actual evidence and functional scope

The reproducible exporter reads existing immutable captures without editing them. Eleven payloads are copied unchanged: ten Hero steps (including one unsaved old-version query) plus the existing AMD `dev-09` calculation. Ten saved executions appear in History. Eleven original-byte identities are hash-checked; only the cited physical PDF pages are rendered for previews. Full PDF copies remain ignored local assets. Original payloads, source/version/build IDs, quotes, coverage and run/parent identities remain available through exact JSON export.

The five walkthroughs expose common-equity ranking; latest-reviewed versus as-reported Tesla quarters; supported WFC facts with difference/full ranking withheld; Tesla Q1/Q2 period-bound generated/unreviewed narrative; and saved original → reviewed parent-linked rerun → old-version query. The last walkthrough is a preserved controlled local import, not a live URL refresh. The extra calculation exposes the saved `+6.61%` receipt, original fiscal intervals, normalized operands, formula and full backend precision. UI code groups decimal digits and positions bars; it does not recompute or authorize financial results/rankings/revisions. Only claim-bound citations are numbered in the narrative; all 18 candidate passages remain in its exact export.

Validation: production static build; independent exact fixture/source-hash checks; browser walkthroughs of citation switching, original pages, keyboard resize, all Heroes, Library filters/empty state, History search/pagination/reopen and narrow evidence navigation. See the [check receipt](../evidence/checks/WORKSPACE_DESIGN_20261013.json). Existing backend validation was reused, with 19 focused tests and the five-Hero integrity replay repeated before the authorized backend push.

## Existing backend boundary after approval

The prototypes intentionally render preserved envelopes, not a new live service. After visual approval, a Next.js server boundary can relay the existing owner-scoped private API using a server-only bearer credential. Browser UI must never receive that token or infer authorization from navigation. Existing `/research/questions`, `/research/evidence/runs`, `/research/runs?offset=&search=`, `/research/runs/{id}` and `/research/runs/{id}/rerun` own execution, immutable reopening, staleness and explicit rerun. `/sources`, version/original routes and `/research/collections` own source inventory and pins. Original download uses the authorized server path, not public static source copies. Source editing, ingestion and review remain private administration.

No new planner, extraction pipeline, backend calculations, history database, source-version resolver, cloud deployment or release promotion is part of this design work. Owner visual selection and live API integration remain unvalidated; independent review/holdout gates remain held.
