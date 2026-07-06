"""Convert extraction JSON into Fact rows (deterministic — no LLM here)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from diligence.facts.model import Fact, FactType


def _pence(value: float | None) -> int | None:
    return None if value is None else round(value * 100)


def _date(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def _month_bounds(month: str) -> tuple[dt.date, dt.date]:
    first = dt.date.fromisoformat(month + "-01")
    y, m = (first.year + 1, 1) if first.month == 12 else (first.year, first.month + 1)
    return first, dt.date(y, m, 1) - dt.timedelta(days=1)


def build_facts(doc_type: str, data: dict, *, dataroom: str, tier: str,
                source_doc: str, extractor: str) -> list[Fact]:
    builder = _BUILDERS[doc_type]
    return builder(data, dataroom=dataroom, tier=tier, source_doc=source_doc,
                   extractor=extractor)


def _base(dataroom, tier, doc_type, source_doc, extractor):
    return dict(dataroom=dataroom, tier=tier, doc_type=doc_type,
                source_doc=source_doc, extractor=extractor)


def _statutory(data: dict, **ctx) -> list[Fact]:
    base = _base(ctx["dataroom"], ctx["tier"], "statutory_accounts",
                 ctx["source_doc"], ctx["extractor"])
    fy_end = _date(data["fy_end"])
    fy_start = fy_end.replace(year=fy_end.year - 1) + dt.timedelta(days=1)
    facts = []

    def add(section: dict, key: str, fact_type: FactType):
        leaf = section[key]
        if leaf["value"] is None:
            return
        facts.append(Fact(
            **base, fact_type=fact_type, page=section["page"],
            confidence=leaf["confidence"], value_pence=_pence(leaf["value"]),
            period_start=fy_start, period_end=fy_end,
        ))

    inc = data["income_statement"]
    for key, ft in (("turnover", FactType.STAT_TURNOVER),
                    ("raw_materials", FactType.STAT_RAW_MATERIALS),
                    ("staff_costs", FactType.STAT_STAFF_COSTS),
                    ("depreciation", FactType.STAT_DEPRECIATION),
                    ("other_charges", FactType.STAT_OTHER_CHARGES),
                    ("profit_before_tax", FactType.STAT_PROFIT_BEFORE_TAX),
                    ("tax", FactType.STAT_TAX)):
        add(inc, key, ft)

    bs = data["balance_sheet"]
    for key, ft in (("fixed_assets", FactType.STAT_FIXED_ASSETS),
                    ("current_assets", FactType.STAT_CURRENT_ASSETS),
                    ("creditors_within_year", FactType.STAT_CREDITORS_WITHIN_YEAR),
                    ("creditors_after_year", FactType.STAT_CREDITORS_AFTER_YEAR),
                    ("net_assets", FactType.STAT_NET_ASSETS)):
        add(bs, key, ft)
    if bs.get("accruals_deferred_income", {}).get("value"):
        add(bs, "accruals_deferred_income", FactType.STAT_ACCRUALS_DEFERRED)

    notes = data["notes"]
    for key, ft in (("loan_within_year", FactType.STAT_LOAN_WITHIN_YEAR),
                    ("loan_after_year", FactType.STAT_LOAN_AFTER_YEAR)):
        # Schema is non-nullable (union limit); value 0 = no such note line
        if notes[key]["value"]:
            add(notes, key, ft)
    if notes["average_employees"]:
        facts.append(Fact(
            **base, fact_type=FactType.STAT_AVG_EMPLOYEES, page=notes["page"],
            confidence=1.0, value_num=float(notes["average_employees"]),
            period_start=fy_start, period_end=fy_end,
        ))
    if notes["loan_disclosure"]:
        facts.append(Fact(
            **base, fact_type="stat_loan_disclosure", page=notes["page"],
            confidence=1.0, value_text=notes["loan_disclosure"],
            period_start=fy_start, period_end=fy_end,
        ))
    return facts


_MGMT_FIELDS = (
    ("revenue", FactType.MGMT_REVENUE),
    ("cost_of_sales", FactType.MGMT_COGS),
    ("staff_costs", FactType.MGMT_STAFF_COSTS),
    ("rent", FactType.MGMT_RENT),
    ("overheads", FactType.MGMT_OVERHEADS),
    ("card_fees", FactType.MGMT_CARD_FEES),
    ("depreciation", FactType.MGMT_DEPRECIATION),
    ("loan_interest", FactType.MGMT_LOAN_INTEREST),
    ("net_profit", FactType.MGMT_NET_PROFIT),
)


def _management(data: dict, **ctx) -> list[Fact]:
    base = _base(ctx["dataroom"], ctx["tier"], "management_pnl",
                 ctx["source_doc"], ctx["extractor"])
    facts = []
    for month in data["months"]:
        first, last = _month_bounds(month["month"])
        for key, ft in _MGMT_FIELDS:
            leaf = month[key]
            if leaf["value"] is None:
                continue
            facts.append(Fact(
                **base, fact_type=ft, page=month["page"],
                confidence=leaf["confidence"],
                value_pence=_pence(leaf["value"]),
                period_start=first, period_end=last,
            ))
    return facts


def _bank(data: dict, **ctx) -> list[Fact]:
    base = _base(ctx["dataroom"], ctx["tier"], "bank_statement",
                 ctx["source_doc"], ctx["extractor"])
    start, end = _date(data["period_start"]), _date(data["period_end"])
    facts = [
        Fact(**base, fact_type=FactType.BANK_OPENING_BALANCE, page=1,
             confidence=data["opening_balance"]["confidence"],
             value_pence=_pence(data["opening_balance"]["value"]),
             period_start=start, period_end=end),
        Fact(**base, fact_type=FactType.BANK_CLOSING_BALANCE, page=1,
             confidence=data["closing_balance"]["confidence"],
             value_pence=_pence(data["closing_balance"]["value"]),
             period_start=start, period_end=end),
    ]
    for txn in data["transactions"]:
        paid_in, paid_out = txn["paid_in"], txn["paid_out"]
        amount = paid_in if paid_in else paid_out
        if amount is None:
            continue
        facts.append(Fact(
            **base, fact_type=FactType.BANK_TXN, page=txn["page"],
            confidence=txn["confidence"], value_pence=_pence(amount),
            value_date=_date(txn["date"]),
            period_start=start, period_end=end,
            attrs={"description": txn["description"],
                   "direction": "in" if paid_in else "out",
                   "balance_after": _pence(txn["balance"])},
        ))
    return facts


_VAT_BOXES = (
    ("box1", FactType.VAT_BOX1), ("box2", FactType.VAT_BOX2),
    ("box3", FactType.VAT_BOX3), ("box4", FactType.VAT_BOX4),
    ("box5", FactType.VAT_BOX5), ("box6", FactType.VAT_BOX6),
    ("box7", FactType.VAT_BOX7),
)


def _vat(data: dict, **ctx) -> list[Fact]:
    base = _base(ctx["dataroom"], ctx["tier"], "vat_return",
                 ctx["source_doc"], ctx["extractor"])
    start, end = _date(data["period_start"]), _date(data["period_end"])
    facts = []
    for key, ft in _VAT_BOXES:
        leaf = data[key]
        if leaf["value"] is None:
            continue
        facts.append(Fact(
            **base, fact_type=ft, page=data["page"],
            confidence=leaf["confidence"], value_pence=_pence(leaf["value"]),
            period_start=start, period_end=end,
        ))
    return facts


def _lease(data: dict, **ctx) -> list[Fact]:
    base = _base(ctx["dataroom"], ctx["tier"], "lease",
                 ctx["source_doc"], ctx["extractor"])
    facts = [
        Fact(**base, fact_type=FactType.LEASE_ANNUAL_RENT,
             page=data["rent_page"],
             confidence=data["annual_rent"]["confidence"],
             value_pence=_pence(data["annual_rent"]["value"])),
        Fact(**base, fact_type=FactType.LEASE_START, page=data["rent_page"],
             confidence=1.0, value_date=_date(data["start_date"])),
        Fact(**base, fact_type=FactType.LEASE_TERM_YEARS,
             page=data["rent_page"], confidence=1.0,
             value_num=float(data["term_years"])),
    ]
    brk = data["break_clause"]
    if brk["exists"] and brk["break_date"]:
        facts.append(Fact(
            **base, fact_type=FactType.LEASE_BREAK_DATE, page=brk["page"],
            confidence=brk["confidence"], value_date=_date(brk["break_date"]),
            attrs={"notice_months": brk["notice_months"]},
        ))
        if brk["notice_months"] is not None:
            facts.append(Fact(
                **base, fact_type=FactType.LEASE_BREAK_NOTICE_MONTHS,
                page=brk["page"], confidence=brk["confidence"],
                value_num=float(brk["notice_months"]),
            ))
    if data["rent_review_date"]:
        facts.append(Fact(
            **base, fact_type=FactType.LEASE_RENT_REVIEW_DATE,
            page=data["rent_page"], confidence=1.0,
            value_date=_date(data["rent_review_date"]),
        ))
    lta = data["inside_lta_1954"]
    if lta["value"] is not None:
        facts.append(Fact(
            **base, fact_type=FactType.LEASE_INSIDE_LTA_1954, page=lta["page"],
            confidence=lta["confidence"],
            value_text="inside" if lta["value"] else "outside",
        ))
    return facts


_BUILDERS = {
    "statutory_accounts": _statutory,
    "management_pnl": _management,
    "bank_statement": _bank,
    "vat_return": _vat,
    "lease": _lease,
}


def doc_type_for(filename: str) -> str | None:
    stem = Path(filename).stem
    for prefix, doc_type in (("statutory_accounts", "statutory_accounts"),
                             ("management_pnl", "management_pnl"),
                             ("bank_statement", "bank_statement"),
                             ("vat_return", "vat_return"),
                             ("lease", "lease")):
        if stem.startswith(prefix):
            return doc_type
    return None
