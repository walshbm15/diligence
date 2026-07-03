"""T1.CLAIM_LEDGER — quantitative seller claims vs the actuals."""

from __future__ import annotations

import datetime as dt

from diligence.checks.base import CheckContext, Evidence, Finding, gbp, pct
from diligence.checks.card_recon import CARD_FEE_RATE
from diligence.facts.model import FactType

CHECK_ID = "T1.CLAIM_LEDGER"


def _claim_dates(claim: dict) -> tuple[dt.date | None, dt.date | None]:
    def parse(key):
        v = claim.get(key)
        return dt.date.fromisoformat(str(v)) if v else None

    return parse("period_start"), parse("period_end")


def run(ctx: CheckContext) -> list[Finding]:
    findings = []

    claim = ctx.claim("monthly_revenue_net")
    if claim and claim.get("value_gbp") is not None:
        start, end = _claim_dates(claim)
        if start and end:
            actual, facts = ctx.facts.sum_monthly(FactType.MGMT_REVENUE, start, end)
            if facts:
                claimed = int(claim["value_gbp"])
                div = (claimed - actual) / actual
                if div > ctx.claim_threshold:
                    findings.append(Finding(
                        check_id=CHECK_ID, severity="red",
                        finding=f"Seller says {start:%B %Y} took about "
                                f"{gbp(claimed)}; the management P&L for that "
                                f"month shows {gbp(actual)} ({pct(div)}). The "
                                f"story is bigger than the books.",
                        evidence=(Evidence(doc_id="claims.json", page=1,
                                           value=claim.get("text", "")[:120]),
                                  *(Evidence.from_fact(f) for f in facts)),
                        confidence=min(f.confidence for f in facts),
                        ask_the_seller=f"Walk through {start:%B %Y} takings "
                                       f"day by day against till records — "
                                       f"where does the extra come from?",
                        warranty_suggestion="Record all revenue statements "
                                            "made by the seller in the "
                                            "disclosure letter; price on the "
                                            "documented figures only.",
                        period_start=start, period_end=end,
                        details={"claimed": claimed, "actual": actual},
                    ))

    claim = ctx.claim("weekly_takings_gross")
    if claim and claim.get("value_gbp") is not None:
        start, end = _claim_dates(claim)
        if start and end:
            settl_net, settl_facts = ctx.facts.card_settlements(start, end)
            cash, cash_facts = ctx.facts.cash_deposits(start, end)
            if settl_facts:
                weeks = max(1, round(((end - start).days + 1) / 7))
                observed_weekly = round(
                    (settl_net / (1 - CARD_FEE_RATE) + cash) / weeks)
                claimed = int(claim["value_gbp"])
                div = (claimed - observed_weekly) / observed_weekly
                if div > ctx.claim_threshold:
                    sample = settl_facts[:2] + cash_facts[:2]
                    findings.append(Finding(
                        check_id=CHECK_ID, severity="red",
                        finding=f"Seller claims takings of {gbp(claimed)} a "
                                f"week; banking supports about "
                                f"{gbp(observed_weekly)} ({pct(div)}).",
                        evidence=(Evidence(doc_id="claims.json", page=1,
                                           value=claim.get("text", "")[:120]),
                                  *(Evidence.from_fact(f) for f in sample)),
                        confidence=min(f.confidence for f in sample),
                        ask_the_seller="Reconcile the claimed weekly takings "
                                       "to the bank deposits for any four "
                                       "recent weeks of the seller's choice.",
                        warranty_suggestion="Disclosure letter to state "
                                            "average weekly takings with "
                                            "supporting bank evidence.",
                        period_start=start, period_end=end,
                        details={"claimed": claimed,
                                 "observed": observed_weekly},
                    ))
    return findings
