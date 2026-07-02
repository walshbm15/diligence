# 03 — Reconciliation Check Catalog (UK)

Every check is deterministic SQL/Python over the extracted fact table.
Output shape per finding:

```json
{
  "check_id": "T1.VAT_TRIANGLE",
  "severity": "red | amber | info",
  "finding": "string",
  "evidence": [{"doc_id": "", "page": 0, "bbox": [], "value": ""}],
  "confidence": 0.0,
  "ask_the_seller": "string",
  "warranty_suggestion": "string (SPA warranty / disclosure letter request)"
}
```

## Tier 1 — Revenue truth (deal-killers)
- **T1.VAT_TRIANGLE**: VAT return Box 6 (total outputs) vs P&L revenue vs
  bank deposits, per quarter. Divergence >5% = red, cite quarters. The single
  best fraud detector in a UK data room (MTD makes VAT returns digital and
  quarterly).
- **T1.CARD_RECON**: card processor settlements (Stripe/SumUp/Worldpay) vs
  claimed card/cash revenue mix. Catches cash-heavy businesses inflating
  declared takings, or undeclared cash "added back" verbally.
- **T1.STAT_VS_MGMT**: Companies House statutory accounts vs management
  accounts shown to buyer. Divergence common; always requires explanation.
- **T1.CLAIM_LEDGER**: every quantitative seller claim (from calls/IM,
  e.g. "£40k months in summer") vs monthly actuals.

## Tier 2 — Cost & liability integrity
- **T2.PAYE_RTI**: staff costs in accounts vs PAYE/RTI vs claimed headcount.
  Flags off-books workers AND family on payroll who leave with seller
  (hidden post-sale cost increase).
- **T2.PENSION_AE**: auto-enrolment compliance (common SMB skeleton;
  inherited in share deals).
- **T2.DLA_RELATED_PARTY**: directors' loan account movements; rent paid to
  director-owned property at off-market rates; classic adjusted-EBITDA games.
- **T2.COVID_DEBT**: Bounce Back Loan / CBILS still amortizing on balance
  sheet, routinely glossed over.
- **T2.IR35**: long-term contractor exposure.

## Tier 3 — Legal & structural
- **T3.CHARGES**: Companies House Charges Register vs seller's disclosed
  debt schedule. Undisclosed debenture = severe red.
- **T3.LEASE**: break clauses, rent review dates, dilapidations exposure,
  inside/outside Landlord & Tenant Act 1954 security of tenure.
- **T3.CHANGE_OF_CONTROL**: assignment/CoC clauses in customer & supplier
  contracts.
- **T3.TUPE**: employee transfer analysis for asset deals.
- **T3.DIRECTOR_HISTORY**: disqualifications, prior insolvencies (Gazette),
  phoenix-company patterns.

## Tier 4 — External signals (no seller cooperation needed)
- CCJ search (Registry Trust)
- Winding-up petitions / insolvency notices (The Gazette API)
- Land Registry title checks
- FCA Register (if regulated activity)
- CQC ratings (care sector)
- FSA food hygiene API (hospitality — rating drop is a leading revenue
  indicator)
- Google Places review volume/velocity as demand proxy

## POC scope
Tier 1 (all four) + T3.CHARGES + T3.LEASE (break clause detection only).
