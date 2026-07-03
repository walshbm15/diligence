"""End-to-end scoring: pipeline findings vs the planted mutation log."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from diligence.checks.base import Finding

FY2_START = dt.date(2025, 4, 1)


def _caught(mutation: dict, findings: list[Finding]) -> bool:
    """One matcher per planted mutation id — explicit is honest."""
    mid = mutation["id"]
    check = mutation["check_id"]
    hits = [f for f in findings if f.check_id == check
            and f.severity in ("red", "amber")]

    if mid == "M01_pnl_revenue_inflated":
        return any(f.period_start and f.period_start >= FY2_START
                   and f.severity == "red" for f in hits)
    if mid == "M02_vat_box6_understated":
        qend = dt.date.fromisoformat(mutation["details"]["quarter_end"])
        return any(f.period_end == qend and f.severity == "red" for f in hits)
    if mid == "M03_undisclosed_loan":
        return any(f.severity == "red" for f in hits)
    if mid == "M04_lease_break_moved":
        target = dt.date.fromisoformat(mutation["details"]["break_after"])
        return any(f.details.get("months_to_break") is not None
                   and f.severity == "red" for f in hits
                   if str(target.year) in f.finding)
    if mid == "M05_stat_vs_mgmt_gap":
        return any(f.period_end and f.period_end < FY2_START
                   and f.severity == "red" for f in hits)
    if mid == "M06_seller_claim_inflated":
        return any(f.details.get("claimed") ==
                   mutation["details"]["claimed_pence"] for f in hits)
    if mid == "M07_cash_addback_claim":
        return any(f.details.get("claimed_share") ==
                   mutation["details"]["claimed_ratio"] for f in hits)
    if mid == "M08_vat_payment_short":
        return any(f.details.get("short_pence") ==
                   mutation["details"]["short_by_pence"] for f in hits)
    if mid == "M09_spouse_on_payroll":
        return bool(hits)  # T2 not in POC scope — expected miss
    if mid == "M10_nontrading_deposit":
        return any(f.details.get("amount_pence") ==
                   mutation["details"]["amount_pence"] for f in hits)
    raise ValueError(f"no matcher for mutation {mid}")


@dataclass
class RecallReport:
    caught: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    missed_catchable: list[str] = field(default_factory=list)
    by_severity: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.caught) + len(self.missed)

    def table(self) -> str:
        lines = [f"red-flag recall: {len(self.caught)}/{self.total} planted "
                 f"discrepancies caught"]
        for sev, (c, t) in sorted(self.by_severity.items()):
            lines.append(f"  {sev:6} {c}/{t}")
        for mid in self.missed:
            tag = ("EXPECTED MISS (check outside POC scope)"
                   if mid not in self.missed_catchable else "MISSED")
            lines.append(f"  {tag}: {mid}")
        return "\n".join(lines)


def score_recall(mutation_log: list[dict],
                 findings: list[Finding]) -> RecallReport:
    report = RecallReport()
    sev_counts: dict[str, list[int]] = {}
    for mutation in mutation_log:
        sev = mutation["severity"]
        counts = sev_counts.setdefault(sev, [0, 0])
        counts[1] += 1
        if _caught(mutation, findings):
            report.caught.append(mutation["id"])
            counts[0] += 1
        else:
            report.missed.append(mutation["id"])
            if mutation.get("catchable_in_poc", True):
                report.missed_catchable.append(mutation["id"])
    report.by_severity = {s: (c, t) for s, (c, t) in sev_counts.items()}
    return report


def citation_violations(findings: list[Finding],
                        documents: set[str]) -> list[str]:
    """A finding citing a document that doesn't exist = hallucination."""
    virtual = {"claims.json", "companies_house:charges"}
    out = []
    for f in findings:
        for e in f.evidence:
            if e.doc_id not in documents and e.doc_id not in virtual:
                out.append(f"{f.check_id} cites non-existent {e.doc_id}")
    return out
