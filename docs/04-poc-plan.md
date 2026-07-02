# 04 — One-Month POC Plan

## Goal
ONE artifact: a cited Red Flag Report on a realistic UK data room, good
enough that a real buyer says "I'd pay for this" — plus eval numbers proving
it isn't a lucky demo. Not a product: no auth, no billing, no dashboard.

## Scope cuts
- One archetype: café/hospitality (abundant, messy, cash-risk-rich)
- Five doc types: statutory accounts, management P&L, bank statements,
  VAT returns, lease
- Checks: Tier 1 (all) + T3.CHARGES + T3.LEASE break-clause
- Front end: CLI or Streamlit; report: generated PDF

## Week 1 — Ground truth FIRST (eval-driven development)
- Model one fictional café at the LEDGER level: 24 months of transactions.
- Render the 5 doc types FROM the ledger using real UK formats
  (Companies House micro-entity accounts layout, HMRC VAT return,
  scanned-quality bank statement). Documents are internally consistent by
  construction.
- Mutation engine: inject 8–10 known discrepancies from a typed taxonomy,
  e.g.: P&L revenue 11% above deposits; VAT Box 6 mismatch Q3; undisclosed
  £40k loan; spouse on payroll; lease break clause month 9. The mutation log
  IS the ground truth.
- Wire Companies House + Gazette APIs against a few real companies (free;
  instant demo credibility).
- EXIT: a data room where every answer is known.

## Week 2 — Extraction spine
- Postgres fact table:
  `fact(id, type, value, unit, period, source_doc, page, bbox, confidence)`
- Extraction via Claude API with PDF input, structured JSON output per doc
  type (fastest POC path; ColQwen/self-hosted later only if unit cost
  demands).
- Measure extraction accuracy against the known ledger IMMEDIATELY,
  stratified: clean digital PDF vs scanned vs photographed.
- EXIT: ≥95% field-level accuracy on clean docs, measured per doc type.

## Week 3 — Reconciliation + report
- Tier 1 checks as plain SQL/Python over the fact table; Charges Register
  cross-check; lease break-clause detection.
- Report generator: severity-ranked findings, each with evidence citations,
  "what to ask the seller," "what warranty to request." Invest in report
  design — it is the entire perceived product.
- EXIT: ≥8/10 planted discrepancies caught; ZERO hallucinated findings;
  a report PDF worth emailing.

## Week 4 — Validation with humans
- Run pipeline on one REAL data room (broker's dead listing, friend's
  business). Fix what breaks — scanned documents are where POCs die.
- Show report to 5–10 people: 3+ prospective/recent UK buyers (UK ETA
  community, Rightbiz/BusinessesForSale, Searchfunder UK), 2 accountants,
  1–2 brokers.
- Ask exactly two questions:
  1. "Would you have paid for this on your last deal — how much?"
  2. "What's missing that would make you distrust it?"
- EXIT: ≥3 people independently name a price ≥£300; no accountant finds a
  factual error.

## Kill criteria (pre-committed — see 02-stress-test.md)
Scanned-doc extraction stuck <85%; interviews converge on "only my
accountant"; <3 people at ≥£300 → pivot to accountant-tool model.

## Costs & effort
Solo-doable in a focused month; with 2 people split generator+evals /
extraction+report. API costs likely under £200.

## Month 2 (if POC passes)
Design partners (free reports for feedback + eval data), ACA-reviewed
premium tier, Tier 2 checks, seller-call ingestion (Whisper + claim
extraction), PI insurance, Cyber Essentials.
