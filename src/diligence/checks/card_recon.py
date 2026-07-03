"""T1.CARD_RECON — card settlements vs the claimed card/cash mix.

Card processor settlements are third-party evidence. If the seller claims a
much lower card share than the settlements support, the difference is
'cash the accounts never saw' — the classic verbal add-back.
"""

from __future__ import annotations

from diligence.checks.base import CheckContext, Evidence, Finding, gbp

CHECK_ID = "T1.CARD_RECON"
CARD_FEE_RATE = 0.0169  # typical SMB card processor fee, used to gross up


def run(ctx: CheckContext) -> list[Finding]:
    latest = ctx.facts.latest_period_end
    if latest is None:
        return []
    claim = ctx.claim("card_share")
    if claim is None or claim.get("value_ratio") is None:
        return []

    import datetime as dt

    start = (dt.date.fromisoformat(str(claim["period_start"]))
             if claim.get("period_start") else latest.replace(year=latest.year - 1))
    end = (dt.date.fromisoformat(str(claim["period_end"]))
           if claim.get("period_end") else latest)

    settl_net, settl_facts = ctx.facts.card_settlements(start, end)
    cash, cash_facts = ctx.facts.cash_deposits(start, end)
    if not settl_net or not (settl_facts or cash_facts):
        return []

    settl_gross = round(settl_net / (1 - CARD_FEE_RATE))
    observed_share = settl_gross / (settl_gross + cash)
    claimed = float(claim["value_ratio"])
    gap = observed_share - claimed
    if abs(gap) <= ctx.card_share_threshold:
        return []

    # The seller claiming a LOWER card share than observed implies extra
    # unbanked cash on top of recorded takings.
    implied_total = round(settl_gross / claimed)
    implied_cash = implied_total - settl_gross
    sample = settl_facts[:2] + cash_facts[:2]
    return [Finding(
        check_id=CHECK_ID, severity="red",
        finding=f"Seller claims {claimed:.0%} of takings go through the card "
                f"machine, but settlements ({gbp(settl_gross)} grossed up) vs "
                f"banked cash ({gbp(cash)}) show {observed_share:.0%} card. At "
                f"the claimed mix there would be {gbp(implied_cash)} of cash — "
                f"{gbp(implied_cash - cash)} of it never banked and outside "
                f"the accounts. Unverifiable cash cannot support the price.",
        evidence=(Evidence(doc_id="claims.json", page=1,
                           value=claim.get("text", "")[:120]),
                  *(Evidence.from_fact(f) for f in sample)),
        confidence=min((f.confidence for f in sample), default=1.0),
        ask_the_seller="Provide 12 months of card processor statements and "
                       "till Z-reports so the card/cash mix can be verified "
                       "independently of the bank account.",
        warranty_suggestion="Price on verifiable revenue only; warranty that "
                            "the accounts include all takings, with a "
                            "specific disclosure of any cash income not "
                            "banked.",
        period_start=start, period_end=end,
        details={"observed_share": observed_share, "claimed_share": claimed},
    )]
