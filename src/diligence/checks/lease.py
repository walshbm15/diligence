"""T3.LEASE — break clause horizon (POC scope: break detection only)."""

from __future__ import annotations

from diligence.checks.base import CheckContext, Evidence, Finding
from diligence.facts.model import FactType

CHECK_ID = "T3.LEASE"


def _months_between(a, b) -> float:
    return (b - a).days / 30.44


def run(ctx: CheckContext) -> list[Finding]:
    findings = []
    brk = ctx.facts.scalar(FactType.LEASE_BREAK_DATE)
    if brk and brk.value_date:
        months = _months_between(ctx.today, brk.value_date)
        notice = brk.attrs.get("notice_months")
        notice_txt = (f" on only {notice} months' notice"
                      if notice is not None else "")
        if months <= 12:
            severity = "red"
        elif months <= 24:
            severity = "amber"
        else:
            severity = "info"
        findings.append(Finding(
            check_id=CHECK_ID, severity=severity,
            finding=f"The lease can be terminated on {brk.value_date:%d %B %Y} "
                    f"— roughly {months:.0f} months after completion —"
                    f"{notice_txt}. The premises ARE the business; a landlord "
                    f"break this early puts the entire purchase at risk.",
            evidence=(Evidence.from_fact(brk, "Break date"),),
            confidence=brk.confidence,
            ask_the_seller="Has the landlord given any indication of "
                           "intentions at the break? Request a meeting with "
                           "the landlord and seek a reversionary lease or "
                           "break waiver before exchange.",
            warranty_suggestion="Make the purchase conditional on the "
                                "landlord waiving the break or granting a "
                                "new lease; otherwise price the business as "
                                "having months of secure tenure, not years.",
            details={"months_to_break": months, "notice_months": notice},
        ))

    lta = ctx.facts.scalar(FactType.LEASE_INSIDE_LTA_1954)
    if lta and lta.value_text == "outside":
        findings.append(Finding(
            check_id=CHECK_ID, severity="amber",
            finding="The lease is contracted OUT of the Landlord and Tenant "
                    "Act 1954 — no automatic right to renew at expiry.",
            evidence=(Evidence.from_fact(lta, "1954 Act status"),),
            confidence=lta.confidence,
            ask_the_seller="What are the landlord's intentions at lease "
                           "expiry, and on what terms would a new lease be "
                           "granted?",
            warranty_suggestion="Seek an agreement for lease or landlord "
                                "comfort letter as a condition of purchase.",
            details={},
        ))
    return findings
