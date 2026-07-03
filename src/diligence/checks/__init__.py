"""Reconciliation checks (POC scope: Tier 1 + T3.CHARGES + T3.LEASE)."""

import datetime as dt

from diligence.checks import (
    card_recon,
    charges,
    claim_ledger,
    lease,
    stat_vs_mgmt,
    vat_triangle,
)
from diligence.checks.base import CheckContext, Evidence, FactIndex, Finding

ALL_CHECKS = (vat_triangle, card_recon, stat_vs_mgmt, claim_ledger,
              charges, lease)

_SEVERITY_ORDER = {"red": 0, "amber": 1, "info": 2}


def run_all(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check.run(ctx))
    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity],
                                 f.check_id, f.period_start or dt.date.min))
    return findings


__all__ = ["ALL_CHECKS", "CheckContext", "Evidence", "FactIndex", "Finding",
           "run_all"]
