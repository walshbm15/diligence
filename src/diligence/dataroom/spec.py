"""Document-level view of the data room.

`build_spec(ledger)` derives one mutable data structure per document from
the (immutable, truthful) ledger. Renderers consume the spec; the mutation
engine edits the spec BEFORE rendering. That mirrors reality: a dishonest
seller's ledger happened one way, but the documents shown to the buyer
disagree with each other.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from diligence.ledger.aggregates import (
    BalanceSheet,
    Pnl,
    balance_sheet,
    bank_lines,
    ct_charge,
    financial_years,
    monthly_pnls,
    vat_returns,
)
from diligence.ledger.models import CafeConfig, LeaseTerms, Ledger


@dataclass
class CompanyInfo:
    name: str
    number: str
    registered_office: str
    director: str


@dataclass
class PnlRow:
    period_start: dt.date
    period_end: dt.date
    revenue: int
    cogs: int
    staff_costs: int
    rent: int
    overheads: int
    card_fees: int
    depreciation: int
    loan_interest: int

    @classmethod
    def from_pnl(cls, p: Pnl) -> PnlRow:
        return cls(p.period_start, p.period_end, p.revenue, p.cogs, p.staff_costs,
                   p.rent, p.overheads, p.card_fees, p.depreciation, p.loan_interest)

    @property
    def gross_profit(self) -> int:
        return self.revenue - self.cogs

    @property
    def profit_before_tax(self) -> int:
        return (self.revenue - self.cogs - self.staff_costs - self.rent
                - self.overheads - self.card_fees - self.depreciation
                - self.loan_interest)


@dataclass
class BalanceSheetData:
    at: dt.date
    fixed_assets: int
    stock: int
    debtors: int
    cash: int
    creditors_within_year: int
    creditors_after_year: int
    share_capital: int
    retained_earnings: int
    # Creditor notes (must sum to the creditor totals in an honest room)
    note_vat: int = 0
    note_paye: int = 0
    note_ct: int = 0
    note_loan_within_year: int = 0
    note_loan_after_year: int = 0

    @classmethod
    def from_bs(cls, b: BalanceSheet, *, note_vat: int, note_paye: int,
                note_ct: int, note_loan_within: int) -> BalanceSheetData:
        return cls(
            at=b.at, fixed_assets=b.fixed_assets, stock=b.stock,
            debtors=b.debtors, cash=b.cash,
            creditors_within_year=b.creditors_within_year,
            creditors_after_year=b.creditors_after_year,
            share_capital=b.share_capital, retained_earnings=b.retained_earnings,
            note_vat=note_vat, note_paye=note_paye, note_ct=note_ct,
            note_loan_within_year=note_loan_within,
            note_loan_after_year=b.creditors_after_year,
        )


@dataclass
class StatutoryAccountsData:
    """Micro-entity (FRS 105) accounts for one financial year.

    All monetary fields are whole pounds expressed in pence (multiples of
    100), as filed accounts are. Totals are computed from the rounded lines
    so the rendered document ties exactly in pounds.
    """
    fy_start: dt.date
    fy_end: dt.date
    turnover: int
    raw_materials: int  # cost of raw materials and consumables (FRS 105 line)
    other_charges: int  # rent, overheads, card fees, loan interest
    staff_costs: int
    depreciation: int
    profit_before_tax: int
    tax: int
    balance: BalanceSheetData
    prior: BalanceSheetData | None  # comparative column
    prior_income: StatutoryAccountsData | None  # P&L comparative
    average_employees: int
    loan_disclosure: str | None  # creditors note text; None = not disclosed


@dataclass
class ManagementPnlData:
    months: list[PnlRow]


@dataclass
class BankLineData:
    date: dt.date
    description: str
    paid_in: int
    paid_out: int
    balance: int


@dataclass
class BankStatementData:
    """One calendar month of statement lines."""
    period_start: dt.date
    period_end: dt.date
    opening_balance: int
    closing_balance: int
    lines: list[BankLineData]
    account_name: str = ""
    sort_code: str = "40-32-16"
    account_number: str = "71449283"


@dataclass
class VatReturnData:
    period_start: dt.date
    period_end: dt.date
    box1: int
    box2: int
    box3: int
    box4: int
    box5: int
    box6: int  # whole pounds on the rendered form
    box7: int


@dataclass
class LeaseData:
    landlord: str
    tenant: str
    premises: str
    start: dt.date
    term_years: int
    annual_rent: int
    break_date: dt.date | None
    break_notice_months: int
    rent_review_date: dt.date
    inside_lta_1954: bool

    @classmethod
    def from_terms(cls, terms: LeaseTerms, tenant: str) -> LeaseData:
        return cls(
            landlord=terms.landlord, tenant=tenant, premises=terms.premises,
            start=terms.start, term_years=terms.term_years,
            annual_rent=terms.annual_rent, break_date=terms.break_date,
            break_notice_months=terms.break_notice_months,
            rent_review_date=terms.rent_review_date,
            inside_lta_1954=terms.inside_lta_1954,
        )


@dataclass
class DataRoomSpec:
    company: CompanyInfo
    statutory_accounts: list[StatutoryAccountsData]  # one per FY
    management_pnl: ManagementPnlData
    bank_statements: list[BankStatementData]  # one per month
    vat_returns: list[VatReturnData]  # one per quarter
    lease: LeaseData
    mutations: list[dict] = field(default_factory=list)  # applied mutation log


def _round_pounds(pence: int) -> int:
    """Round to whole pounds, still expressed in pence."""
    return round(pence / 100) * 100


def _stat_accounts_for_fy(ledger: Ledger, fy_start: dt.date, fy_end: dt.date,
                          prior: BalanceSheetData | None) -> StatutoryAccountsData:
    from diligence.ledger.aggregates import (
        _ct_accrual_at,
        _loan_principal_due_within,
        _paye_accrual_at,
        _vat_accrual_at,
        pnl,
    )
    from diligence.ledger.generator import loan_balance_at

    cfg = ledger.config
    p = pnl(ledger.transactions, cfg, fy_start, fy_end)
    bs = balance_sheet(ledger, fy_end)
    loan_within = _loan_principal_due_within(cfg, fy_end)

    pounds = _round_pounds
    # Round balance sheet lines to whole pounds; force the tie by deriving
    # retained earnings from the rounded net assets (as filed accounts do).
    note_vat = pounds(_vat_accrual_at(ledger, fy_end))
    note_paye = pounds(_paye_accrual_at(ledger, fy_end))
    note_ct = pounds(_ct_accrual_at(ledger, fy_end))
    note_loan_within = pounds(loan_within)
    creditors_within = note_vat + note_paye + note_ct + note_loan_within
    creditors_after = pounds(bs.creditors_after_year)
    fixed = pounds(bs.fixed_assets)
    stock = pounds(bs.stock)
    debtors = pounds(bs.debtors)
    cash = pounds(bs.cash)
    net_assets = (fixed + stock + debtors + cash
                  - creditors_within - creditors_after)
    bs_data = BalanceSheetData(
        at=bs.at, fixed_assets=fixed, stock=stock, debtors=debtors, cash=cash,
        creditors_within_year=creditors_within,
        creditors_after_year=creditors_after,
        share_capital=bs.share_capital,
        retained_earnings=net_assets - bs.share_capital,
        note_vat=note_vat, note_paye=note_paye, note_ct=note_ct,
        note_loan_within_year=note_loan_within,
        note_loan_after_year=creditors_after,
    )
    loan_total = loan_balance_at(cfg, fy_end)
    # Round P&L lines; derive PBT/profit from the rounded lines.
    turnover = pounds(p.revenue)
    raw_materials = pounds(p.cogs)
    staff = pounds(p.staff_costs)
    dep = pounds(p.depreciation)
    other = pounds(p.rent + p.overheads + p.card_fees + p.loan_interest)
    tax = pounds(ct_charge(ledger, fy_start, fy_end))
    return StatutoryAccountsData(
        fy_start=fy_start, fy_end=fy_end,
        turnover=turnover,
        raw_materials=raw_materials,
        other_charges=other,
        staff_costs=staff,
        depreciation=dep,
        profit_before_tax=turnover - raw_materials - staff - dep - other,
        tax=tax,
        balance=bs_data,
        prior=prior,
        prior_income=None,
        average_employees=len(cfg.employees),
        loan_disclosure=(
            f"Included in creditors is a bank loan of £{loan_total / 100:,.0f} "
            f"from {cfg.loan.lender}, secured by a fixed and floating charge "
            f"over the assets of the company, repayable in monthly instalments "
            f"to {cfg.loan.start.year + cfg.loan.term_months // 12}."
        ),
    )


def _synthetic_prior_year(cfg: CafeConfig, first_bs: BalanceSheetData) -> BalanceSheetData:
    """Plausible FY(-1) comparative for the first statutory accounts.

    The pre-window year has no ledger; these figures are scaled, rounded
    constants. No reconciliation check targets them.
    """
    day_before = cfg.start - dt.timedelta(days=1)
    from diligence.ledger.generator import loan_balance_at, monthly_paye_bill

    pounds = _round_pounds
    loan_bal = pounds(loan_balance_at(cfg, day_before))
    loan_within = 7_000_00
    note_vat = pounds(cfg.opening_vat_liability)
    note_paye = pounds(monthly_paye_bill(cfg))
    note_ct = pounds(cfg.opening_ct_liability)
    creditors_within = note_vat + note_paye + note_ct + loan_within
    fixed = pounds(cfg.fixed_asset_nbv(day_before))
    net_assets = (fixed + cfg.stock_value + cfg.opening_bank_balance
                  - creditors_within - (loan_bal - loan_within))
    return BalanceSheetData(
        at=day_before,
        fixed_assets=fixed,
        stock=cfg.stock_value,
        debtors=0,
        cash=cfg.opening_bank_balance,
        creditors_within_year=creditors_within,
        creditors_after_year=loan_bal - loan_within,
        share_capital=cfg.share_capital,
        retained_earnings=net_assets - cfg.share_capital,
        note_vat=note_vat,
        note_paye=note_paye,
        note_ct=note_ct,
        note_loan_within_year=loan_within,
        note_loan_after_year=loan_bal - loan_within,
    )


def build_spec(ledger: Ledger) -> DataRoomSpec:
    cfg = ledger.config
    company = CompanyInfo(
        name=cfg.company_name,
        number=cfg.company_number,
        registered_office=cfg.lease.premises,
        director="Margaret Holt",
    )

    fys = financial_years(cfg)
    stat_accounts: list[StatutoryAccountsData] = []
    prior: BalanceSheetData | None = None
    for fy_start, fy_end in fys:
        acc = _stat_accounts_for_fy(ledger, fy_start, fy_end, prior)
        if prior is None:
            acc.prior = _synthetic_prior_year(cfg, acc.balance)
        else:
            acc.prior_income = stat_accounts[-1]
        stat_accounts.append(acc)
        prior = acc.balance

    mgmt = ManagementPnlData(months=[PnlRow.from_pnl(p) for p in monthly_pnls(ledger)])

    # Bank statements: split running lines by calendar month
    from diligence.ledger.generator import month_range

    all_lines = bank_lines(ledger)
    statements = []
    balance_before = cfg.opening_bank_balance
    for first, last in month_range(cfg.start, cfg.months):
        month_lines = [BankLineData(line.date, line.description, line.paid_in,
                                    line.paid_out, line.balance)
                       for line in all_lines if first <= line.date <= last]
        closing = month_lines[-1].balance if month_lines else balance_before
        statements.append(BankStatementData(
            period_start=first, period_end=last,
            opening_balance=balance_before, closing_balance=closing,
            lines=month_lines, account_name=cfg.company_name.upper(),
        ))
        balance_before = closing

    vats = [VatReturnData(
        period_start=r.period_start, period_end=r.period_end,
        box1=r.box1, box2=r.box2, box3=r.box3, box4=r.box4,
        box5=r.box5, box6=round(r.box6 / 100) * 100, box7=round(r.box7 / 100) * 100,
    ) for r in vat_returns(ledger)]

    return DataRoomSpec(
        company=company,
        statutory_accounts=stat_accounts,
        management_pnl=mgmt,
        bank_statements=statements,
        vat_returns=vats,
        lease=LeaseData.from_terms(cfg.lease, tenant=cfg.company_name),
    )
