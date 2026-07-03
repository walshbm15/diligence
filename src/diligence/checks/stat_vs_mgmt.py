"""T1.STAT_VS_MGMT — statutory accounts vs management accounts, per FY."""

from __future__ import annotations

from diligence.checks.base import CheckContext, Evidence, Finding, gbp, pct
from diligence.facts.model import FactType

CHECK_ID = "T1.STAT_VS_MGMT"


def run(ctx: CheckContext) -> list[Finding]:
    findings = []
    for stat in sorted(ctx.facts.of(FactType.STAT_TURNOVER),
                       key=lambda f: f.period_end):
        fy_start, fy_end = stat.period_start, stat.period_end
        mgmt_rev, mgmt_facts = ctx.facts.sum_monthly(
            FactType.MGMT_REVENUE, fy_start, fy_end)
        if not mgmt_facts:
            continue
        div = (mgmt_rev - stat.value_pence) / stat.value_pence
        if abs(div) <= ctx.amber_threshold:
            continue
        severity = "red" if abs(div) > ctx.red_threshold else "amber"
        higher = "management accounts" if div > 0 else "filed accounts"
        findings.append(Finding(
            check_id=CHECK_ID, severity=severity,
            finding=f"FYE {fy_end:%b %Y}: turnover filed at Companies House is "
                    f"{gbp(stat.value_pence)} but the management P&L for the "
                    f"same 12 months totals {gbp(mgmt_rev)} ({pct(div)}). The "
                    f"{higher} show more revenue — either the buyer is being "
                    f"shown inflated figures or HMRC was shown deflated ones.",
            evidence=(Evidence.from_fact(stat, "Filed turnover"),
                      *(Evidence.from_fact(f, f"{f.period_start:%b %y}")
                        for f in mgmt_facts[:6])),
            confidence=min(f.confidence for f in (stat, *mgmt_facts)),
            ask_the_seller="Provide the year-end journal/reconciliation from "
                           "management accounts to statutory accounts, and "
                           "the accountant's working papers.",
            warranty_suggestion="Warranty that the management accounts fairly "
                                "present performance and reconcile to the "
                                "filed accounts; consider completion accounts "
                                "rather than a locked-box price.",
            period_start=fy_start, period_end=fy_end,
            details={"divergence": div},
        ))
    return findings
