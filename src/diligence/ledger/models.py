"""Ledger data model.

The ledger is the single source of truth for the synthetic data room: every
document is rendered FROM it, so every number in the data room is derivable
and every eval answer is known. All monetary values are integer pence.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum


class TxnType(StrEnum):
    SALE = "sale"  # daily till takings (not a bank movement)
    CARD_SETTLEMENT = "card_settlement"  # processor payout into bank
    CASH_DEPOSIT = "cash_deposit"  # weekly cash banking
    SUPPLIER_PAYMENT = "supplier_payment"
    PAYROLL_NET = "payroll_net"  # net pay to an employee
    HMRC_PAYE = "hmrc_paye"  # PAYE + NI remitted to HMRC
    RENT = "rent"
    VAT_PAYMENT = "vat_payment"
    LOAN_REPAYMENT = "loan_repayment"
    CORPORATION_TAX = "corporation_tax"
    DIVIDEND = "dividend"


# Transaction types that move money through the bank account.
BANK_TYPES = frozenset(TxnType) - {TxnType.SALE}

# Bank inflows; everything else in BANK_TYPES is an outflow.
INFLOW_TYPES = frozenset({TxnType.CARD_SETTLEMENT, TxnType.CASH_DEPOSIT})


@dataclass(frozen=True)
class Transaction:
    date: dt.date
    type: TxnType
    description: str
    amount: int  # pence; positive magnitude, direction implied by type
    counterparty: str = ""
    # For SALE rows: split of the day's gross takings.
    card_gross: int = 0
    cash_gross: int = 0
    vat: int = 0  # output VAT within a SALE, input VAT within a supplier payment
    interest: int = 0  # interest portion of a LOAN_REPAYMENT


@dataclass(frozen=True)
class Employee:
    name: str
    role: str
    monthly_gross: int  # pence


@dataclass(frozen=True)
class Loan:
    lender: str
    principal: int  # pence
    annual_rate: float
    start: dt.date
    term_months: int
    charge_id: str  # Companies House charge reference


@dataclass(frozen=True)
class LeaseTerms:
    landlord: str
    premises: str
    start: dt.date
    term_years: int
    annual_rent: int  # pence
    break_date: dt.date | None
    break_notice_months: int
    rent_review_date: dt.date
    inside_lta_1954: bool = True  # security of tenure


@dataclass(frozen=True)
class CafeConfig:
    seed: int = 20260401
    company_name: str = "The Copper Kettle Café Ltd"
    company_number: str = "13977581"
    # `start` must be the first day of a month AND the first month of a VAT
    # quarter — quarters are consecutive 3-month blocks from `start`, so the
    # start month IS the VAT stagger (start June => quarters end
    # Aug/Nov/Feb/May). `months` must be a multiple of 3 so every VAT
    # quarter in the window is complete.
    start: dt.date = dt.date(2024, 4, 1)
    months: int = 24
    # Month the financial year ends in (3 = 31 March). FYs are derived
    # independently of the window; only FYs fully inside the window get
    # statutory accounts.
    fye_month: int = 3
    opening_bank_balance: int = 30_000_00
    share_capital: int = 100_00

    # Opening liabilities carried into the window (paid at their statutory
    # due dates: VAT ~5 weeks into the window, CT at pre-window FYE + 9mo + 1d).
    opening_vat_liability: int = 6_410_00  # quarter ending just before start
    opening_ct_liability: int = 7_820_00  # pre-window FYE

    # Sales model
    base_daily_takings: int = 1_150_00  # gross pence, pre-factor
    card_share: float = 0.78
    standard_rated_share: float = 0.85  # of gross takings (rest zero-rated)
    card_fee_rate: float = 0.0169  # SumUp
    processor_name: str = "SUMUP PAYOUTS"

    # Fixed assets (fit-out & equipment) — straight line
    fixed_asset_cost: int = 35_000_00
    fixed_asset_acquired: dt.date = dt.date(2021, 10, 1)
    fixed_asset_life_years: int = 8
    stock_value: int = 2_500_00  # constant stock assumption

    # People
    employees: tuple[Employee, ...] = (
        Employee("Margaret Holt", "Director", 1_000_00),
        Employee("Priya Sharma", "Manager", 2_200_00),
        Employee("Daniel Okafor", "Chef", 1_900_00),
        Employee("Jake Timms", "Barista", 1_450_00),
        Employee("Sofia Marino", "Barista", 1_380_00),
        Employee("Ellie Watson", "Barista", 1_340_00),
        Employee("Tom Bradley", "Barista (PT)", 1_310_00),
    )

    # Debt
    loan: Loan = Loan(
        lender="Funding Circle Ltd",
        principal=40_000_00,
        annual_rate=0.075,
        start=dt.date(2023, 6, 15),
        term_months=60,
        charge_id="139775810001",
    )

    lease: LeaseTerms = LeaseTerms(
        landlord="Bridgnorth Estates LLP",
        premises="14 Wharf Street, Shrewsbury SY1 1LN",
        start=dt.date(2021, 9, 29),
        term_years=10,
        annual_rent=26_000_00,
        break_date=None,  # clean lease has no break; mutation M04 plants one
        break_notice_months=6,
        rent_review_date=dt.date(2026, 9, 29),
        inside_lta_1954=True,
    )

    dividend_quarterly: int = 6_000_00
    corporation_tax_rate: float = 0.19  # small profits rate

    def __post_init__(self) -> None:
        if self.start.day != 1:
            raise ValueError("start must be the first day of a month")
        if self.months % 3 != 0:
            raise ValueError("months must be a multiple of 3 (whole VAT "
                             "quarters)")
        if not 1 <= self.fye_month <= 12:
            raise ValueError("fye_month must be 1-12")

    @property
    def end(self) -> dt.date:
        y, m = self.start.year, self.start.month - 1 + self.months
        y, m = y + m // 12, m % 12 + 1
        return dt.date(y, m, 1) - dt.timedelta(days=1)

    @property
    def monthly_depreciation(self) -> int:
        return round(self.fixed_asset_cost / (self.fixed_asset_life_years * 12))

    def fixed_asset_nbv(self, at: dt.date) -> int:
        months = ((at.year - self.fixed_asset_acquired.year) * 12
                  + at.month - self.fixed_asset_acquired.month + 1)
        months = max(0, min(months, self.fixed_asset_life_years * 12))
        return self.fixed_asset_cost - months * self.monthly_depreciation


@dataclass
class Ledger:
    config: CafeConfig
    transactions: list[Transaction] = field(default_factory=list)

    def in_period(self, start: dt.date, end: dt.date) -> list[Transaction]:
        return [t for t in self.transactions if start <= t.date <= end]

    def of_type(self, *types: TxnType) -> list[Transaction]:
        wanted = set(types)
        return [t for t in self.transactions if t.type in wanted]
