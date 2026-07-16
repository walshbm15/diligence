"""Derived financial views over the ledger.

Everything a document renderer needs — monthly P&L, quarterly VAT boxes,
bank statement lines, micro-entity accounts — is computed here from the
transaction list alone (plus config constants). Integer pence throughout;
the balance sheet ties exactly, by construction, at financial year ends.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from diligence.ledger.generator import (
    COGS_SUPPLIERS,
    amortization_schedule,
    ct_slices,
    financial_years,
    loan_balance_at,
    month_range,
    monthly_paye_bill,
    paye_breakdown,
    quarter_ranges,
)

__all__ = ["financial_years", "quarter_ranges"]  # re-exported period helpers
from diligence.ledger.models import (
    INFLOW_TYPES,
    CafeConfig,
    Ledger,
    Transaction,
    TxnType,
)

# --- P&L -------------------------------------------------------------------


@dataclass(frozen=True)
class Pnl:
    period_start: dt.date
    period_end: dt.date
    revenue: int  # net of VAT
    cogs: int
    staff_costs: int  # gross wages + employer NI
    rent: int
    overheads: int  # net of recoverable input VAT
    card_fees: int
    depreciation: int
    loan_interest: int

    @property
    def gross_profit(self) -> int:
        return self.revenue - self.cogs

    @property
    def profit_before_tax(self) -> int:
        return (self.revenue - self.cogs - self.staff_costs - self.rent
                - self.overheads - self.card_fees - self.depreciation
                - self.loan_interest)


def _months_between(start: dt.date, end: dt.date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def staff_cost_monthly(cfg: CafeConfig) -> int:
    """Gross wages + employer NI per month (constant roster)."""
    total = 0
    for emp in cfg.employees:
        _tax, _ee, er_ni = paye_breakdown(emp.monthly_gross)
        total += emp.monthly_gross + er_ni
    return total


def pnl(txns: list[Transaction], cfg: CafeConfig,
        start: dt.date, end: dt.date) -> Pnl:
    """P&L for a whole-month-aligned period."""
    period = [t for t in txns if start <= t.date <= end]
    sales = [t for t in period if t.type == TxnType.SALE]
    supplier = [t for t in period if t.type == TxnType.SUPPLIER_PAYMENT]
    n_months = _months_between(start, end)

    revenue = sum(t.amount - t.vat for t in sales)
    cogs = sum(t.amount - t.vat for t in supplier if t.counterparty in COGS_SUPPLIERS)
    overheads = sum(t.amount - t.vat for t in supplier
                    if t.counterparty not in COGS_SUPPLIERS)
    card_fees = sum(round(t.card_gross * cfg.card_fee_rate) for t in sales)
    rent = sum(t.amount for t in period if t.type == TxnType.RENT)
    interest = sum(t.interest for t in period if t.type == TxnType.LOAN_REPAYMENT)
    return Pnl(
        period_start=start, period_end=end,
        revenue=revenue, cogs=cogs,
        staff_costs=n_months * staff_cost_monthly(cfg),
        rent=rent, overheads=overheads, card_fees=card_fees,
        depreciation=n_months * cfg.monthly_depreciation,
        loan_interest=interest,
    )


def profit_before_tax(txns: list[Transaction], cfg: CafeConfig,
                      start: dt.date, end: dt.date) -> int:
    return pnl(txns, cfg, start, end).profit_before_tax


def monthly_pnls(ledger: Ledger) -> list[Pnl]:
    cfg = ledger.config
    return [pnl(ledger.transactions, cfg, first, last)
            for first, last in month_range(cfg.start, cfg.months)]


# --- VAT returns -------------------------------------------------------------


@dataclass(frozen=True)
class VatReturn:
    period_start: dt.date
    period_end: dt.date
    box1: int  # VAT due on sales
    box4: int  # VAT reclaimed on purchases
    box6: int  # total value of sales ex VAT (whole pounds on the form)
    box7: int  # total value of purchases ex VAT

    @property
    def box2(self) -> int:
        return 0  # no EU acquisitions

    @property
    def box3(self) -> int:
        return self.box1 + self.box2

    @property
    def box5(self) -> int:
        return self.box3 - self.box4

    @property
    def box8(self) -> int:
        return 0

    @property
    def box9(self) -> int:
        return 0


def vat_returns(ledger: Ledger) -> list[VatReturn]:
    out = []
    for qstart, qend in quarter_ranges(ledger.config):
        q = ledger.in_period(qstart, qend)
        sales = [t for t in q if t.type == TxnType.SALE]
        supplier = [t for t in q if t.type == TxnType.SUPPLIER_PAYMENT]
        out.append(VatReturn(
            period_start=qstart, period_end=qend,
            box1=sum(t.vat for t in sales),
            box4=sum(t.vat for t in supplier),
            box6=sum(t.amount - t.vat for t in sales),
            box7=sum(t.amount - t.vat for t in supplier),
        ))
    return out


# --- Bank statement -----------------------------------------------------------


@dataclass(frozen=True)
class BankLine:
    date: dt.date
    description: str
    paid_in: int
    paid_out: int
    balance: int  # running balance after this line


def bank_lines(ledger: Ledger) -> list[BankLine]:
    balance = ledger.config.opening_bank_balance
    lines = []
    for t in ledger.transactions:
        if t.type == TxnType.SALE:
            continue
        if t.type in INFLOW_TYPES:
            balance += t.amount
            lines.append(BankLine(t.date, t.description, t.amount, 0, balance))
        else:
            balance -= t.amount
            lines.append(BankLine(t.date, t.description, 0, t.amount, balance))
    return lines


def bank_balance_at(ledger: Ledger, at: dt.date) -> int:
    balance = ledger.config.opening_bank_balance
    for t in ledger.transactions:
        if t.type == TxnType.SALE or t.date > at:
            continue
        balance += t.amount if t.type in INFLOW_TYPES else -t.amount
    return balance


# --- Financial years / statutory accounts --------------------------------------


def ct_charge(ledger: Ledger, fy_start: dt.date, fy_end: dt.date) -> int:
    cfg = ledger.config
    pbt = profit_before_tax(ledger.transactions, cfg, fy_start, fy_end)
    return max(0, round(pbt * cfg.corporation_tax_rate))


def _card_debtor_at(ledger: Ledger, at: dt.date) -> int:
    """Card takings settled by SumUp after `at` (money in transit)."""
    cfg = ledger.config
    earned = sum(t.card_gross - round(t.card_gross * cfg.card_fee_rate)
                 for t in ledger.transactions
                 if t.type == TxnType.SALE and t.date <= at)
    received = sum(t.amount for t in ledger.transactions
                   if t.type == TxnType.CARD_SETTLEMENT and t.date <= at)
    return earned - received


def _till_cash_at(ledger: Ledger, at: dt.date) -> int:
    taken = sum(t.cash_gross for t in ledger.transactions
                if t.type == TxnType.SALE and t.date <= at)
    banked = sum(t.amount for t in ledger.transactions
                 if t.type == TxnType.CASH_DEPOSIT and t.date <= at)
    return taken - banked


def _vat_accrual_at(ledger: Ledger, at: dt.date) -> int:
    """VAT liability accrues transaction-by-transaction, not by quarter —
    a balance sheet drawn mid-quarter (FYE off the VAT stagger) must carry
    the partial quarter's net VAT. At quarter ends this equals the old
    whole-quarter accrual exactly."""
    cfg = ledger.config
    accrued = cfg.opening_vat_liability
    for t in ledger.transactions:
        if t.date > at:
            continue
        if t.type == TxnType.SALE:
            accrued += t.vat
        elif t.type == TxnType.SUPPLIER_PAYMENT:
            accrued -= t.vat
    paid = sum(t.amount for t in ledger.transactions
               if t.type == TxnType.VAT_PAYMENT and t.date <= at)
    return accrued - paid


def _paye_accrual_at(ledger: Ledger, at: dt.date) -> int:
    cfg = ledger.config
    bill = monthly_paye_bill(cfg)
    months_accrued = sum(1 for _first, last in month_range(cfg.start, cfg.months)
                         if last <= at)
    accrued = bill + months_accrued * bill  # opening month + window months
    paid = sum(t.amount for t in ledger.transactions
               if t.type == TxnType.HMRC_PAYE and t.date <= at)
    return accrued - paid


def _ct_accrual_at(ledger: Ledger, at: dt.date) -> int:
    cfg = ledger.config
    accrued = cfg.opening_ct_liability
    for slice_start, slice_end in ct_slices(cfg):
        if slice_end <= at:
            accrued += ct_charge(ledger, slice_start, slice_end)
    paid = sum(t.amount for t in ledger.transactions
               if t.type == TxnType.CORPORATION_TAX and t.date <= at)
    return accrued - paid


def _loan_principal_due_within(cfg: CafeConfig, at: dt.date, months: int = 12) -> int:
    horizon = dt.date(at.year + (at.month + months - 1) // 12,
                      (at.month + months - 1) % 12 + 1, 28)
    due = 0
    for pay_date, pay, interest, _bal in amortization_schedule(
            cfg.loan.principal, cfg.loan.annual_rate, cfg.loan.term_months, cfg.loan.start):
        if at < pay_date <= horizon:
            due += pay - interest
    return due


def opening_retained_earnings(cfg: CafeConfig) -> int:
    """Derived so that the opening balance sheet ties exactly."""
    day_before = cfg.start - dt.timedelta(days=1)
    assets = (cfg.opening_bank_balance + cfg.stock_value
              + cfg.fixed_asset_nbv(day_before))
    liabilities = (loan_balance_at(cfg, day_before)
                   + cfg.opening_vat_liability
                   + monthly_paye_bill(cfg)  # last pre-window month, unpaid
                   + cfg.opening_ct_liability)
    return assets - liabilities - cfg.share_capital


@dataclass(frozen=True)
class BalanceSheet:
    at: dt.date
    fixed_assets: int
    stock: int
    debtors: int
    cash: int  # bank + till
    creditors_within_year: int
    creditors_after_year: int
    share_capital: int
    retained_earnings: int

    @property
    def net_assets(self) -> int:
        return (self.fixed_assets + self.stock + self.debtors + self.cash
                - self.creditors_within_year - self.creditors_after_year)

    @property
    def capital_and_reserves(self) -> int:
        return self.share_capital + self.retained_earnings


def balance_sheet(ledger: Ledger, at: dt.date) -> BalanceSheet:
    """Balance sheet at a financial year end (valid only at FYE dates)."""
    cfg = ledger.config
    loan_bal = loan_balance_at(cfg, at)
    loan_current = _loan_principal_due_within(cfg, at)

    # Profit accrues from the WINDOW start (where opening retained earnings
    # are defined), not from the first full FY — a window that starts mid-FY
    # has a stub whose profit is in the assets and must be in reserves too.
    retained = opening_retained_earnings(cfg)
    retained += profit_before_tax(ledger.transactions, cfg, cfg.start, at)
    for slice_start, slice_end in ct_slices(cfg):
        if slice_end <= at:
            retained -= ct_charge(ledger, slice_start, slice_end)
    retained -= sum(t.amount for t in ledger.transactions
                    if t.type == TxnType.DIVIDEND and t.date <= at)

    return BalanceSheet(
        at=at,
        fixed_assets=cfg.fixed_asset_nbv(at),
        stock=cfg.stock_value,
        debtors=_card_debtor_at(ledger, at),
        cash=bank_balance_at(ledger, at) + _till_cash_at(ledger, at),
        creditors_within_year=(_vat_accrual_at(ledger, at)
                               + _paye_accrual_at(ledger, at)
                               + _ct_accrual_at(ledger, at)
                               + loan_current),
        creditors_after_year=loan_bal - loan_current,
        share_capital=cfg.share_capital,
        retained_earnings=retained,
    )
