# Development metric definitions — policy v1

This is the curation policy for the [frozen development inventory](fixtures/product/development_inventory.v1.json), not automatic semantic certification. A reviewer must attest every original metric/table column, actual interval, scale, currency, scope, basis and report identity before importing an eligible card. Independent second review is required for release-critical facts/calculations and revision mappings. No acquired file alone authorizes an answer.

| Metric | Binding and comparison rule |
| --- | --- |
| `revenue` | Consolidated issuer-reported total revenue. For WFC, document net interest income + noninterest income and the bank's presentation. Do not compare bank revenue to AMD/Tesla revenue as economically equivalent without an explicit reviewed definition. |
| `net_income` | Preserve existing legacy cards; record exact original attribution. Never silently map parent-attributable, common-shareholder or consolidated income into one comparison. |
| `net_income_parent` | New mapping for income attributable to the parent; exclude common-shareholder-only values. Tesla/WFC FY2024 compatibility remains held until exact rows and attribution are independently reviewed. |
| `gross_profit`, `gross_margin`, `operating_income` | Original reported values; GAAP/non-GAAP remain distinct. A margin calculation uses a same-company, same-interval, same-scope/basis revenue denominator; computed percentages differ from rounded reported percentages. |
| `net_interest_income`, `provision_credit_losses` | WFC bank-specific lines; distinguish provision expense from allowance balance and net charge-offs. Negative provision is not a missing value. |
| `vehicle_production`, `vehicle_deliveries` | Tesla original counts, basis `operating`, scope `consolidated`; same-period counts for ratios/differences. A production/delivery difference is not proven inventory movement. |
| Segment revenue (`revenue`, scope `segment:<definition>`) | Retain segment membership/presentation epoch in the scope, e.g. `segment:client_gaming_2025`. AMD's 2025 combined Client/Gaming presentation requires a separately reviewed retrospective comparable view; a scope change is not a dimension-preserving fact revision. |

AMD fiscal periods require actual filing boundaries and calendar `amd_52_53_week`; Tesla/WFC calendar periods use `calendar`. Do not substitute fiscal labels for dates, use annual as Q4, infer quarter from YTD subtraction, or align AMD to calendar issuers automatically. Unequal trend durations require an explicit reporting-kind calculation policy and visible qualification. Ratios/counts never acquire GAAP labels merely to fit a form.

Each review record must identify report family/accession, raw hash, indexed original page/window, build, role links, actual interval and review revision. Generated captions/context and extracted candidates are not original evidence. Keep publication cutoff, financial restatement, segment reclassification and metadata correction separate. Retain all unresolved conflicts; do not promote based on publication recency. Same values repeated in companion decks/filings are not independent multi-document successes.

The service enforces its existing typed dimension/location/arithmetic contracts. This policy adds human curation requirements; it does not claim a new economically equivalent metric classifier or permission to auto-promote facts.
