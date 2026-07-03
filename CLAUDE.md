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

## Build status (updated 2026-07-03 — keep current when closing issues)
Weeks 1–3 of the POC are BUILT and merged; GitHub issues #1–#7, #9–#16
closed. CI green. Do not rebuild these — extend them.

**Code map:** `src/diligence/` — `ledger/` (seeded 24-month café ledger,
integer pence, balance sheet ties exactly), `dataroom/` (spec builder +
room builder; mutations edit the spec, never the ledger), `render/`
(5 UK doc types via reportlab + scanned/photographed degradation),
`mutations/` (10 planted discrepancies, `mutation_log.json` = eval ground
truth), `facts/` (Postgres fact table, provenance NOT NULL), `extraction/`
(Claude structured outputs, per-field confidence, <0.8 quarantined),
`checks/` (6 deterministic checks: T1 x4 + T3.CHARGES + T3.LEASE),
`report/` (HTML→PDF via headless Chrome, sufficiency score first),
`evals/` (ground truth from spec, recall + accuracy scorers),
`external/` (Companies House + Gazette clients + per-room fixture).

**Measured (check layer, ground-truth facts):** 9/10 mutations caught,
7/7 red, 0 false positives on clean room, 0 hallucinated citations.
Week 3 exit criterion met.

**Open issues & blockers:**
- #8 — live extraction accuracy (Week 2 exit: ≥95% clean/doc type).
  BLOCKED on `ANTHROPIC_API_KEY` in `.env`. Run:
  `docker compose up -d && .venv/bin/pytest evals/test_extraction_accuracy.py -s`
- #17 — real data room run (needs real documents from Brian)
- #18 — 5–10 validation interviews, two questions only, price test
- #19 — Month 1 gate decision record (go/pivot/kill against
  pre-committed criteria; fill in AFTER #8/#17/#18). Do NOT create
  Month 2 issues until #19 is decided — interview Q2 answers are the
  backlog input.

**Local dev:** Python 3.12 venv at `.venv` (pyenv 3.12.12), Postgres
17-alpine via `docker compose up -d` (port 5433), `pytest` runs tests +
evals, `ruff check .` must pass. Commands: `diligence generate` (build
synthetic rooms into data_rooms/), `diligence extract <room> --tier X`,
`diligence report <room> [--ground-truth]` (credential-free demo →
output/*.pdf).
