"""Document sufficiency score — the report's FIRST section.

'We could not verify X because Y is missing' is a deliverable, not a
failure state. Scores what fraction of the expected evidence base was
actually present and readable.
"""

from __future__ import annotations

from dataclasses import dataclass

from diligence.checks.base import FactIndex
from diligence.facts.model import FactType


@dataclass(frozen=True)
class SufficiencyItem:
    label: str
    have: int
    want: int

    @property
    def ratio(self) -> float:
        return min(1.0, self.have / self.want) if self.want else 1.0

    @property
    def complete(self) -> bool:
        return self.have >= self.want


@dataclass(frozen=True)
class SufficiencyReport:
    items: tuple[SufficiencyItem, ...]
    needs_review: int  # facts below the confidence threshold

    @property
    def score(self) -> int:
        if not self.items:
            return 0
        return round(100 * sum(i.ratio for i in self.items) / len(self.items))

    @property
    def gaps(self) -> list[str]:
        out = [f"{i.label}: {i.have} of {i.want} present"
               for i in self.items if not i.complete]
        if self.needs_review:
            out.append(f"{self.needs_review} extracted figures were too "
                       f"unclear to use and need human verification")
        return out


def assess(facts: FactIndex, needs_review: int = 0,
           expected_bank_months: int = 24, expected_vat_quarters: int = 8,
           expected_fys: int = 2) -> SufficiencyReport:
    bank_docs = {f.source_doc for f in facts.of(FactType.BANK_CLOSING_BALANCE)}
    vat_docs = {f.source_doc for f in facts.of(FactType.VAT_BOX6)}
    # Presence marker is a balance-sheet line: small companies legally file
    # without a P&L, so turnover's absence doesn't mean the accounts are
    # missing (learned from a real CH filing).
    stat_docs = {f.source_doc for f in facts.of(FactType.STAT_NET_ASSETS)}
    mgmt_months = {f.period_start for f in facts.of(FactType.MGMT_REVENUE)}
    lease = 1 if facts.of(FactType.LEASE_ANNUAL_RENT) else 0

    items = (
        SufficiencyItem("Bank statements (months)", len(bank_docs),
                        expected_bank_months),
        SufficiencyItem("VAT returns (quarters)", len(vat_docs),
                        expected_vat_quarters),
        SufficiencyItem("Statutory accounts (years)", len(stat_docs),
                        expected_fys),
        SufficiencyItem("Management P&L (months)", len(mgmt_months),
                        expected_bank_months),
        SufficiencyItem("Lease", lease, 1),
    )
    return SufficiencyReport(items=items, needs_review=needs_review)
