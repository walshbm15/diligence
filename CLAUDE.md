# Diligence OS — Project Context for Claude Code

## What this is
An AI due-diligence engine for UK small-business acquisitions (sub-£2M deals).
A buyer uploads a seller's data room (statutory accounts, management accounts,
bank statements, VAT returns, lease, payroll, seller call recordings). A
pipeline of extraction + deterministic reconciliation checks + external
verification agents produces a cited **Red Flag Report**: every finding traced
to a source page, with "what to ask the seller" and "what SPA warranty to
request."

**Core thesis:** due diligence is a *reconciliation* problem. The same revenue
must appear (transformed) in the tax filings, P&L, VAT returns, and bank
deposits. Software that hunts for where these *disagree* — rather than
summarizing documents — does not exist for the UK SMB segment.

## Golden rules (architecture principles — do not violate)
1. **LLMs extract and interpret; deterministic code reconciles and computes.**
   Never let an LLM do arithmetic that a SQL query over the fact table can do.
2. **Every fact carries provenance** (source doc, page, bbox, confidence).
   Every report finding must cite provenance. No citation → no finding.
3. **Eval-driven development.** The synthetic data room with planted
   discrepancies is built BEFORE extraction code. All changes run against the
   eval suite in CI. Headline metric: red-flag recall by severity tier.
   Second metric: false-positive rate (accountant trust depends on it).
4. **When extraction confidence is low, prompt for human verification —
   never guess.** This is also the liability posture.

## Current phase: 1-month POC
See docs/04-poc-plan.md. Scope: ONE archetype (café/hospitality), FIVE doc
types (statutory accounts, management P&L, bank statements, VAT returns,
lease), Tier 1 checks + 2 Tier 3 checks, Streamlit/CLI front end, PDF report.
No auth, no billing, no dashboard.

## Stack decisions (POC)
- Python, Postgres (+ pgvector later; not needed for POC)
- Extraction: Claude API with PDF input, structured JSON outputs per doc type
  (swap to ColQwen/self-hosted later only if unit cost demands)
- Reconciliation: plain SQL/Python over the fact table
- External data: Companies House API (free), The Gazette API (free)
- Orchestration: simple pipeline for POC; LangGraph when agents multiply
- Report: HTML → PDF (design matters — the report IS the product)
- Evals: pytest-based harness comparing pipeline output to the known
  mutation log of the synthetic data room

## Key UK-specific product features
- **VAT triangle check** (Box 6 outputs vs P&L revenue vs bank deposits,
  quarterly) — the single best fraud detector in a UK data room
- **Charges Register cross-check** (Companies House) vs seller's disclosed debts
- Findings map to **SPA warranty/disclosure-letter suggestions** (UK deals are
  often share purchases — buyer inherits all historical liabilities)
- "Document sufficiency score" as first output; insufficient records is a
  useful deliverable, not a failure state

## Docs index
- docs/01-project-brief.md — idea, market evidence, business model
- docs/02-stress-test.md — competition, risks, honest weaknesses, kill criteria
- docs/03-check-catalog.md — full reconciliation check catalog (Tiers 1–4)
- docs/04-poc-plan.md — week-by-week 1-month POC plan with exit criteria
- docs/05-architecture.md — target system architecture (post-POC)
