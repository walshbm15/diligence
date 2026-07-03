"""Fact model: the boundary between LLM extraction and deterministic checks.

Every fact carries provenance (source doc, page, bbox, confidence) — a fact
without provenance cannot exist (enforced at the schema level too). Facts
below CONFIDENCE_REVIEW_THRESHOLD are flagged for human verification and
excluded from checks; the pipeline never guesses.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

CONFIDENCE_REVIEW_THRESHOLD = 0.8


class FactType(StrEnum):
    # Statutory accounts (whole-pound figures, pence representation)
    STAT_TURNOVER = "stat_turnover"
    STAT_RAW_MATERIALS = "stat_raw_materials"
    STAT_STAFF_COSTS = "stat_staff_costs"
    STAT_DEPRECIATION = "stat_depreciation"
    STAT_OTHER_CHARGES = "stat_other_charges"
    STAT_PROFIT_BEFORE_TAX = "stat_profit_before_tax"
    STAT_TAX = "stat_tax"
    STAT_FIXED_ASSETS = "stat_fixed_assets"
    STAT_CURRENT_ASSETS = "stat_current_assets"
    STAT_CREDITORS_WITHIN_YEAR = "stat_creditors_within_year"
    STAT_CREDITORS_AFTER_YEAR = "stat_creditors_after_year"
    STAT_NET_ASSETS = "stat_net_assets"
    STAT_LOAN_WITHIN_YEAR = "stat_loan_within_year"
    STAT_LOAN_AFTER_YEAR = "stat_loan_after_year"
    STAT_AVG_EMPLOYEES = "stat_avg_employees"

    # Management P&L (per month)
    MGMT_REVENUE = "mgmt_revenue"
    MGMT_COGS = "mgmt_cogs"
    MGMT_STAFF_COSTS = "mgmt_staff_costs"
    MGMT_RENT = "mgmt_rent"
    MGMT_OVERHEADS = "mgmt_overheads"
    MGMT_CARD_FEES = "mgmt_card_fees"
    MGMT_DEPRECIATION = "mgmt_depreciation"
    MGMT_LOAN_INTEREST = "mgmt_loan_interest"
    MGMT_NET_PROFIT = "mgmt_net_profit"

    # Bank statements (per line + per statement)
    BANK_TXN = "bank_txn"  # attrs: description, direction
    BANK_OPENING_BALANCE = "bank_opening_balance"
    BANK_CLOSING_BALANCE = "bank_closing_balance"

    # VAT returns (per quarter)
    VAT_BOX1 = "vat_box1"
    VAT_BOX2 = "vat_box2"
    VAT_BOX3 = "vat_box3"
    VAT_BOX4 = "vat_box4"
    VAT_BOX5 = "vat_box5"
    VAT_BOX6 = "vat_box6"
    VAT_BOX7 = "vat_box7"

    # Lease
    LEASE_ANNUAL_RENT = "lease_annual_rent"
    LEASE_START = "lease_start"
    LEASE_TERM_YEARS = "lease_term_years"
    LEASE_BREAK_DATE = "lease_break_date"
    LEASE_BREAK_NOTICE_MONTHS = "lease_break_notice_months"
    LEASE_RENT_REVIEW_DATE = "lease_rent_review_date"
    LEASE_INSIDE_LTA_1954 = "lease_inside_lta_1954"


@dataclass(frozen=True)
class Fact:
    dataroom: str
    tier: str  # clean | scanned | photographed | ground_truth
    doc_type: str  # statutory_accounts | management_pnl | bank_statement | vat_return | lease
    fact_type: str
    source_doc: str  # provenance: file name — required
    page: int  # provenance: 1-based page — required
    confidence: float
    value_pence: int | None = None
    value_num: float | None = None
    value_text: str | None = None
    value_date: dt.date | None = None
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    attrs: dict = field(default_factory=dict)
    bbox: tuple[float, float, float, float] | None = None
    extractor: str = ""

    def __post_init__(self):
        if not self.source_doc or self.page < 1:
            raise ValueError("fact without provenance (source_doc, page)")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")

    @property
    def needs_review(self) -> bool:
        return self.confidence < CONFIDENCE_REVIEW_THRESHOLD
