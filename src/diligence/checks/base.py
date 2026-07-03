"""Shared machinery for reconciliation checks.

Checks are pure functions over extracted facts (+ seller claims and the
Companies House register). They never call an LLM and never do arithmetic
an accountant couldn't replicate. A Finding without evidence cannot be
constructed — golden rule 2 enforced structurally.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any

from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD, Fact, FactType


@dataclass(frozen=True)
class Evidence:
    doc_id: str
    page: int
    value: str

    @classmethod
    def from_fact(cls, f: Fact, label: str | None = None) -> Evidence:
        if f.value_pence is not None:
            value = f"£{f.value_pence / 100:,.2f}"
        elif f.value_date is not None:
            value = str(f.value_date)
        elif f.value_num is not None:
            value = f"{f.value_num:g}"
        else:
            value = f.value_text or ""
        if label:
            value = f"{label}: {value}"
        return cls(doc_id=f.source_doc, page=f.page, value=value)


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: str  # red | amber | info
    finding: str
    evidence: tuple[Evidence, ...]
    confidence: float
    ask_the_seller: str
    warranty_suggestion: str
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.evidence:
            raise ValueError(f"{self.check_id}: finding without evidence")
        if self.severity not in ("red", "amber", "info"):
            raise ValueError(f"bad severity {self.severity}")


def gbp(pence: int) -> str:
    return f"£{pence / 100:,.0f}"


def pct(x: float) -> str:
    return f"{x:+.1%}"


CARD_SETTLEMENT_RE = re.compile(r"SUMUP|STRIPE|WORLDPAY|SQUARE|ZETTLE", re.I)
CASH_DEPOSIT_RE = re.compile(r"CASH", re.I)
HMRC_VAT_RE = re.compile(r"HMRC VAT", re.I)
LOAN_RE = re.compile(r"FUNDING CIRCLE|LOAN|IWOCA|FLEXILOAN", re.I)


class FactIndex:
    """Query surface over confident facts (low-confidence facts excluded —
    they are queued for human review, never silently used)."""

    def __init__(self, facts: list[Fact],
                 min_confidence: float = CONFIDENCE_REVIEW_THRESHOLD):
        self.all = [f for f in facts if f.confidence >= min_confidence]
        self._by_type: dict[str, list[Fact]] = {}
        for f in self.all:
            self._by_type.setdefault(f.fact_type, []).append(f)

    def of(self, fact_type: str) -> list[Fact]:
        return self._by_type.get(fact_type, [])

    def scalar(self, fact_type: str, period_end: dt.date | None = None) -> Fact | None:
        for f in self.of(fact_type):
            if period_end is None or f.period_end == period_end:
                return f
        return None

    def sum_monthly(self, fact_type: str, start: dt.date, end: dt.date
                    ) -> tuple[int, list[Fact]]:
        hits = [f for f in self.of(fact_type)
                if f.period_start and start <= f.period_start <= end]
        return sum(f.value_pence for f in hits), hits

    # --- bank transaction categories ------------------------------------

    def _txns(self, pattern: re.Pattern, direction: str,
              start: dt.date, end: dt.date) -> list[Fact]:
        return [f for f in self.of(FactType.BANK_TXN)
                if f.attrs.get("direction") == direction
                and f.value_date and start <= f.value_date <= end
                and pattern.search(f.attrs.get("description", ""))]

    def card_settlements(self, start: dt.date, end: dt.date) -> tuple[int, list[Fact]]:
        hits = self._txns(CARD_SETTLEMENT_RE, "in", start, end)
        return sum(f.value_pence for f in hits), hits

    def cash_deposits(self, start: dt.date, end: dt.date) -> tuple[int, list[Fact]]:
        hits = self._txns(CASH_DEPOSIT_RE, "in", start, end)
        return sum(f.value_pence for f in hits), hits

    def vat_payments(self, start: dt.date, end: dt.date) -> list[Fact]:
        return self._txns(HMRC_VAT_RE, "out", start, end)

    def loan_repayments(self) -> list[Fact]:
        return [f for f in self.of(FactType.BANK_TXN)
                if f.attrs.get("direction") == "out"
                and LOAN_RE.search(f.attrs.get("description", ""))]

    @property
    def latest_period_end(self) -> dt.date | None:
        dates = [f.period_end for f in self.all if f.period_end]
        return max(dates) if dates else None


@dataclass
class CheckContext:
    facts: FactIndex
    claims: list[dict] = field(default_factory=list)
    companies_house: Any = None  # CompaniesHouseClient | CompaniesHouseFixture
    company_number: str = ""
    # Divergence thresholds (fractions)
    red_threshold: float = 0.05
    amber_threshold: float = 0.02
    claim_threshold: float = 0.10
    card_share_threshold: float = 0.08
    reference_date: dt.date | None = None  # "today" for lease horizon checks

    def claim(self, metric: str) -> dict | None:
        for c in self.claims:
            if c.get("metric") == metric:
                return c
        return None

    @property
    def today(self) -> dt.date:
        if self.reference_date:
            return self.reference_date
        latest = self.facts.latest_period_end
        return (latest + dt.timedelta(days=90)) if latest else dt.date.today()
