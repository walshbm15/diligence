"""T1.VAT_TRIANGLE — VAT Box 6 vs P&L revenue vs bank deposits, quarterly.

Three deterministic legs per VAT quarter:
  (a) Box 6 vs management P&L revenue (both net of VAT — direct compare)
  (b) banked takings vs P&L gross implied by the return's own VAT rate
  (c) the bank payment to HMRC vs Box 5 on the return
"""

from __future__ import annotations

import datetime as dt

from diligence.checks.base import CheckContext, Evidence, Finding, gbp, pct
from diligence.facts.model import FactType

CHECK_ID = "T1.VAT_TRIANGLE"
FEE_AND_LAG_ALLOWANCE = 0.03  # card fees ~1.7% + settlement timing at quarter edges
NON_TRADING_CREDIT_FLOOR = 2_500_00  # pence


def _non_trading_credits(ctx: CheckContext) -> list[Finding]:
    """(d) Large credits that are neither card settlements nor cash banking.

    Catches deposit-padding directly, even when another distortion (e.g.
    inflated P&L revenue) makes the quarterly totals cancel out.
    """
    from diligence.checks.base import CARD_SETTLEMENT_RE, CASH_DEPOSIT_RE
    from diligence.facts.model import FactType

    findings = []
    for f in ctx.facts.of(FactType.BANK_TXN):
        desc = f.attrs.get("description", "")
        if (f.attrs.get("direction") == "in"
                and f.value_pence >= NON_TRADING_CREDIT_FLOOR
                and not CARD_SETTLEMENT_RE.search(desc)
                and not CASH_DEPOSIT_RE.search(desc)):
            findings.append(Finding(
                check_id=CHECK_ID, severity="amber",
                finding=f"{f.value_date:%d %b %Y}: {gbp(f.value_pence)} "
                        f"credited as “{desc}” — not card takings, "
                        f"not cash banking. Non-trading money inflates the "
                        f"apparent cash generation of the business.",
                evidence=(Evidence.from_fact(f, desc),),
                confidence=f.confidence,
                ask_the_seller=f"What is the {gbp(f.value_pence)} credit of "
                               f"{f.value_date:%d %B %Y}, and are there "
                               f"other non-trading receipts in the period?",
                warranty_suggestion="Disclosure letter to list all "
                                    "non-trading credits to the business "
                                    "account; adjust any cash-flow-based "
                                    "valuation accordingly.",
                period_start=f.period_start, period_end=f.period_end,
                details={"amount_pence": f.value_pence, "description": desc},
            ))
    return findings


def run(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = _non_trading_credits(ctx)
    for box6 in sorted(ctx.facts.of(FactType.VAT_BOX6),
                       key=lambda f: f.period_start):
        qstart, qend = box6.period_start, box6.period_end
        qlabel = f"{qstart:%b}–{qend:%b %Y}"
        mgmt_rev, mgmt_facts = ctx.facts.sum_monthly(
            FactType.MGMT_REVENUE, qstart, qend)
        if not mgmt_facts:
            continue

        # (a) Box 6 vs P&L revenue — both net of VAT
        div = (mgmt_rev - box6.value_pence) / box6.value_pence
        if abs(div) > ctx.red_threshold:
            direction = ("above the VAT return" if div > 0
                         else "below the VAT return")
            findings.append(Finding(
                check_id=CHECK_ID, severity="red",
                finding=f"{qlabel}: management P&L revenue {gbp(mgmt_rev)} is "
                        f"{pct(div)} {direction} Box 6 outputs "
                        f"{gbp(box6.value_pence)}. The same sales must appear "
                        f"in both — one of them is wrong.",
                evidence=(Evidence.from_fact(box6, "VAT Box 6"),
                          *(Evidence.from_fact(f, f"{f.period_start:%b %y} revenue")
                            for f in mgmt_facts)),
                confidence=min(f.confidence for f in (box6, *mgmt_facts)),
                ask_the_seller=f"Reconcile {qlabel} revenue in the management "
                               f"accounts to Box 6 of the VAT return for the "
                               f"same quarter, line by line.",
                warranty_suggestion="Warranty that all VAT returns filed are "
                                    "complete and accurate and that management "
                                    "accounts revenue reconciles to them; "
                                    "indemnity for pre-completion VAT "
                                    "assessments, interest and penalties.",
                period_start=qstart, period_end=qend,
                details={"divergence": div},
            ))

        # (b) banked takings vs implied gross takings
        box1 = ctx.facts.scalar(FactType.VAT_BOX1, period_end=qend)
        settl, settl_facts = ctx.facts.card_settlements(qstart, qend)
        cash, cash_facts = ctx.facts.cash_deposits(qstart, qend)
        deposits = settl + cash
        if box1 and deposits and box6.value_pence:
            vat_rate = box1.value_pence / box6.value_pence
            mgmt_gross = round(mgmt_rev * (1 + vat_rate))
            div = (deposits - mgmt_gross) / mgmt_gross
            sample = (settl_facts[:2] + cash_facts[:2]) or settl_facts or cash_facts
            if div < -(ctx.red_threshold + FEE_AND_LAG_ALLOWANCE):
                findings.append(Finding(
                    check_id=CHECK_ID, severity="red",
                    finding=f"{qlabel}: takings banked ({gbp(deposits)}: card "
                            f"{gbp(settl)} + cash {gbp(cash)}) fall {pct(div)} "
                            f"short of the {gbp(mgmt_gross)} gross implied by "
                            f"the P&L at the return's own VAT rate. Reported "
                            f"revenue is not supported by money received.",
                    evidence=(Evidence.from_fact(box6, "VAT Box 6"),
                              *(Evidence.from_fact(f) for f in sample)),
                    confidence=min(f.confidence for f in (box6, *sample)),
                    ask_the_seller="Where is the revenue that never reached "
                                   "the bank account — other accounts, "
                                   "unbanked cash, or is it not real?",
                    warranty_suggestion="Warranty that all business takings "
                                        "are banked into the disclosed "
                                        "account(s) and that the accounts "
                                        "reflect all receipts.",
                    period_start=qstart, period_end=qend,
                    details={"divergence": div},
                ))
            elif div > ctx.red_threshold:
                findings.append(Finding(
                    check_id=CHECK_ID, severity="amber",
                    finding=f"{qlabel}: {gbp(deposits)} was banked but the "
                            f"P&L plus VAT only supports {gbp(mgmt_gross)} "
                            f"({pct(div)}). Deposits include money that is "
                            f"not recorded trading income.",
                    evidence=(Evidence.from_fact(box6, "VAT Box 6"),
                              *(Evidence.from_fact(f) for f in sample)),
                    confidence=min(f.confidence for f in (box6, *sample)),
                    ask_the_seller="Identify every non-trading credit in the "
                                   "bank statements for this quarter "
                                   "(director money in, refunds, transfers).",
                    warranty_suggestion="Disclosure letter to list all "
                                        "non-trading receipts credited to the "
                                        "business account in the period.",
                    period_start=qstart, period_end=qend,
                    details={"divergence": div},
                ))

        # (c) bank payment to HMRC vs Box 5
        box5 = ctx.facts.scalar(FactType.VAT_BOX5, period_end=qend)
        if box5:
            window_start = qend + dt.timedelta(days=25)
            window_end = qend + dt.timedelta(days=55)
            payments = ctx.facts.vat_payments(window_start, window_end)
            if payments and abs(payments[0].value_pence - box5.value_pence) > 100:
                pay = payments[0]
                short = box5.value_pence - pay.value_pence
                findings.append(Finding(
                    check_id=CHECK_ID, severity="amber",
                    finding=f"{qlabel}: the VAT return shows {gbp(box5.value_pence)} "
                            f"due (Box 5) but the bank shows {gbp(pay.value_pence)} "
                            f"paid — {gbp(abs(short))} "
                            f"{'short' if short > 0 else 'over'}. Possible "
                            f"arrears or undisclosed time-to-pay arrangement.",
                    evidence=(Evidence.from_fact(box5, "VAT Box 5"),
                              Evidence.from_fact(pay, "HMRC payment")),
                    confidence=min(box5.confidence, pay.confidence),
                    ask_the_seller="Provide the HMRC VAT account statement "
                                   "and details of any time-to-pay "
                                   "arrangement or open enquiry.",
                    warranty_suggestion="Warranty that all taxes due have "
                                        "been paid; indemnity for any VAT "
                                        "arrears at completion (buyer "
                                        "inherits them in a share purchase).",
                    period_start=qstart, period_end=qend,
                    details={"short_pence": short},
                ))
    return findings
