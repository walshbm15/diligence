"""T3.CHARGES — Companies House Charges Register vs disclosed borrowings.

The register is external truth the seller cannot edit. An outstanding
charge with no corresponding disclosed borrowing is a severe red flag —
in a share purchase the buyer inherits whatever it secures.
"""

from __future__ import annotations

from diligence.checks.base import CheckContext, Evidence, Finding, gbp
from diligence.facts.model import FactType

CHECK_ID = "T3.CHARGES"


def run(ctx: CheckContext) -> list[Finding]:
    if ctx.companies_house is None or not ctx.company_number:
        return []
    charges = ctx.companies_house.charges(ctx.company_number)
    outstanding = [c for c in charges if c.outstanding]
    if not outstanding:
        return []

    # Disclosed borrowings: loan lines in the latest filed accounts
    loan_facts = (ctx.facts.of(FactType.STAT_LOAN_WITHIN_YEAR)
                  + ctx.facts.of(FactType.STAT_LOAN_AFTER_YEAR))
    latest_fy = max((f.period_end for f in loan_facts), default=None)
    disclosed = sum(f.value_pence for f in loan_facts
                    if f.period_end == latest_fy)
    borrow_claim = ctx.claim("total_borrowings")
    claimed = (int(borrow_claim["value_gbp"])
               if borrow_claim and borrow_claim.get("value_gbp") is not None
               else None)

    repayments = ctx.facts.loan_repayments()
    findings = []
    for charge in outstanding:
        lender = ", ".join(charge.persons_entitled) or "unknown lender"
        register_evidence = Evidence(
            doc_id="companies_house:charges", page=1,
            value=f"Charge {charge.charge_code} ({charge.status}), created "
                  f"{charge.created_on}, in favour of {lender}")
        if disclosed > 0:
            findings.append(Finding(
                check_id=CHECK_ID, severity="info",
                finding=f"Outstanding charge {charge.charge_code} in favour of "
                        f"{lender} is consistent with the {gbp(disclosed)} of "
                        f"bank loans disclosed in the latest filed accounts.",
                evidence=(register_evidence,
                          *(Evidence.from_fact(f) for f in ctx.facts.of(
                              FactType.STAT_LOAN_AFTER_YEAR)[:1])),
                confidence=1.0,
                ask_the_seller="Confirm the outstanding balance and obtain a "
                               "redemption statement before completion.",
                warranty_suggestion="Deed of release or redemption at "
                                    "completion for all registered charges.",
                details={"charge_code": charge.charge_code},
            ))
            continue

        evidence = [register_evidence]
        extra = ""
        if repayments:
            evidence.append(Evidence.from_fact(
                repayments[0], "Monthly repayment still leaving the account"))
            extra = (f" Monthly repayments of "
                     f"{gbp(repayments[0].value_pence)} to {lender} are still "
                     f"visible in the bank statements ({len(repayments)} "
                     f"payments in the period).")
        denial = ""
        if claimed == 0:
            denial = " The seller has stated the business has no borrowings."
            evidence.append(Evidence(doc_id="claims.json", page=1,
                                     value=borrow_claim.get("text", "")[:120]))
        findings.append(Finding(
            check_id=CHECK_ID, severity="red",
            finding=f"Companies House shows an OUTSTANDING charge "
                    f"({charge.charge_code}) in favour of {lender} — "
                    f"{charge.description or 'secured over the company'} — "
                    f"but the accounts disclose no bank borrowings.{extra}"
                    f"{denial} In a share purchase the buyer inherits "
                    f"whatever this secures.",
            evidence=tuple(evidence),
            confidence=min((e.confidence for e in repayments[:1]), default=1.0),
            ask_the_seller=f"What does charge {charge.charge_code} secure, "
                           f"what is the outstanding balance, and why is it "
                           f"not in the accounts?",
            warranty_suggestion="Condition precedent: full redemption "
                                "statement and deed of release for every "
                                "registered charge; indemnity for any "
                                "undisclosed secured liabilities.",
            details={"charge_code": charge.charge_code, "lender": lender},
        ))
    return findings
