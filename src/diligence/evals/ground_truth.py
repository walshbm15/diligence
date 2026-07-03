"""Expected facts derived from the DataRoomSpec.

The spec is exactly what the renderers printed, so it is the ground truth
for extraction: accuracy measures whether the pipeline read what the
documents say. (Whether the documents are *truthful* is the reconciliation
layer's job — mutated rooms have mutated expected facts, by design.)
"""

from __future__ import annotations

from diligence.dataroom.spec import DataRoomSpec
from diligence.facts.model import Fact, FactType

GT_TIER = "ground_truth"


def _round_pounds(pence: int) -> int:
    return round(pence / 100) * 100


def expected_facts(spec: DataRoomSpec, dataroom: str) -> list[Fact]:
    facts: list[Fact] = []
    base = dict(dataroom=dataroom, tier=GT_TIER, confidence=1.0,
                extractor="spec")

    # --- Statutory accounts (rendered in whole pounds) --------------------
    for acc in spec.statutory_accounts:
        doc = f"statutory_accounts_fye{acc.fy_end.year}.pdf"
        ctx = dict(**base, doc_type="statutory_accounts", source_doc=doc,
                   period_start=acc.fy_start, period_end=acc.fy_end)
        b = acc.balance
        scalars = [
            (FactType.STAT_TURNOVER, acc.turnover, 2),
            (FactType.STAT_RAW_MATERIALS, acc.raw_materials, 2),
            (FactType.STAT_STAFF_COSTS, acc.staff_costs, 2),
            (FactType.STAT_DEPRECIATION, acc.depreciation, 2),
            (FactType.STAT_OTHER_CHARGES, acc.other_charges, 2),
            (FactType.STAT_PROFIT_BEFORE_TAX, acc.profit_before_tax, 2),
            (FactType.STAT_TAX, acc.tax, 2),
            (FactType.STAT_FIXED_ASSETS, b.fixed_assets, 3),
            (FactType.STAT_CURRENT_ASSETS, b.stock + b.debtors + b.cash, 3),
            (FactType.STAT_CREDITORS_WITHIN_YEAR, b.creditors_within_year, 3),
            (FactType.STAT_CREDITORS_AFTER_YEAR, b.creditors_after_year, 3),
            (FactType.STAT_NET_ASSETS,
             b.fixed_assets + b.stock + b.debtors + b.cash
             - b.creditors_within_year - b.creditors_after_year, 3),
        ]
        # Loan note lines only exist on the page when non-zero
        if b.note_loan_within_year:
            scalars.append((FactType.STAT_LOAN_WITHIN_YEAR,
                            b.note_loan_within_year, 4))
        if b.note_loan_after_year:
            scalars.append((FactType.STAT_LOAN_AFTER_YEAR,
                            b.note_loan_after_year, 4))
        for ft, pence, page in scalars:
            facts.append(Fact(**ctx, fact_type=ft, value_pence=pence, page=page))
        facts.append(Fact(**ctx, fact_type=FactType.STAT_AVG_EMPLOYEES,
                          value_num=float(acc.average_employees), page=4))

    # --- Management P&L (rendered in whole pounds) ------------------------
    for i, m in enumerate(spec.management_pnl.months):
        page = i // 12 + 1
        ctx = dict(**base, doc_type="management_pnl",
                   source_doc="management_pnl.pdf",
                   period_start=m.period_start, period_end=m.period_end)
        for ft, pence in (
                (FactType.MGMT_REVENUE, m.revenue),
                (FactType.MGMT_COGS, m.cogs),
                (FactType.MGMT_STAFF_COSTS, m.staff_costs),
                (FactType.MGMT_RENT, m.rent),
                (FactType.MGMT_OVERHEADS, m.overheads),
                (FactType.MGMT_CARD_FEES, m.card_fees),
                (FactType.MGMT_DEPRECIATION, m.depreciation),
                (FactType.MGMT_LOAN_INTEREST, m.loan_interest),
                (FactType.MGMT_NET_PROFIT, m.profit_before_tax)):
            facts.append(Fact(**ctx, fact_type=ft,
                              value_pence=_round_pounds(pence), page=page))

    # --- Bank statements (rendered to the penny) ---------------------------
    for stmt in spec.bank_statements:
        doc = f"bank_statement_{stmt.period_start:%Y-%m}.pdf"
        ctx = dict(**base, doc_type="bank_statement", source_doc=doc,
                   period_start=stmt.period_start, period_end=stmt.period_end)
        facts.append(Fact(**ctx, fact_type=FactType.BANK_OPENING_BALANCE,
                          value_pence=stmt.opening_balance, page=1))
        facts.append(Fact(**ctx, fact_type=FactType.BANK_CLOSING_BALANCE,
                          value_pence=stmt.closing_balance, page=1))
        for line in stmt.lines:
            amount = line.paid_in or line.paid_out
            facts.append(Fact(
                **ctx, fact_type=FactType.BANK_TXN, value_pence=amount,
                value_date=line.date, page=1,
                attrs={"description": line.description,
                       "direction": "in" if line.paid_in else "out"},
            ))

    # --- VAT returns --------------------------------------------------------
    for ret in spec.vat_returns:
        doc = f"vat_return_{ret.period_end:%Y-%m}.pdf"
        ctx = dict(**base, doc_type="vat_return", source_doc=doc,
                   period_start=ret.period_start, period_end=ret.period_end)
        for ft, pence in ((FactType.VAT_BOX1, ret.box1),
                          (FactType.VAT_BOX2, ret.box2),
                          (FactType.VAT_BOX3, ret.box3),
                          (FactType.VAT_BOX4, ret.box4),
                          (FactType.VAT_BOX5, ret.box5),
                          (FactType.VAT_BOX6, ret.box6),
                          (FactType.VAT_BOX7, ret.box7)):
            facts.append(Fact(**ctx, fact_type=ft, value_pence=pence, page=1))

    # --- Lease ---------------------------------------------------------------
    lease = spec.lease
    ctx = dict(**base, doc_type="lease", source_doc="lease.pdf")
    facts.append(Fact(**ctx, fact_type=FactType.LEASE_ANNUAL_RENT,
                      value_pence=lease.annual_rent, page=2))
    facts.append(Fact(**ctx, fact_type=FactType.LEASE_START,
                      value_date=lease.start, page=2))
    facts.append(Fact(**ctx, fact_type=FactType.LEASE_TERM_YEARS,
                      value_num=float(lease.term_years), page=2))
    if lease.break_date:
        facts.append(Fact(**ctx, fact_type=FactType.LEASE_BREAK_DATE,
                          value_date=lease.break_date, page=2,
                          attrs={"notice_months": lease.break_notice_months}))
        facts.append(Fact(**ctx, fact_type=FactType.LEASE_BREAK_NOTICE_MONTHS,
                          value_num=float(lease.break_notice_months), page=2))
    facts.append(Fact(**ctx, fact_type=FactType.LEASE_RENT_REVIEW_DATE,
                      value_date=lease.rent_review_date, page=2))
    facts.append(Fact(**ctx, fact_type=FactType.LEASE_INSIDE_LTA_1954,
                      value_text="inside" if lease.inside_lta_1954 else "outside",
                      page=2))
    return facts
