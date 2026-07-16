"""Seeded generator for the fictional café ledger.

Deterministic: the same CafeConfig.seed always produces the identical
transaction list. Money is integer pence; every derived figure (VAT boxes,
P&L lines, bank deposits) traces back to these rows.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from diligence.ledger.models import CafeConfig, Ledger, Transaction, TxnType

# Trading calendar ---------------------------------------------------------

WEEKDAY_FACTOR = {0: 0.82, 1: 0.86, 2: 0.92, 3: 0.98, 4: 1.10, 5: 1.38, 6: 1.18}
# Café seasonality: summer tourists + December; January/February trough.
MONTH_FACTOR = {
    1: 0.80, 2: 0.85, 3: 0.93, 4: 1.00, 5: 1.06, 6: 1.12,
    7: 1.22, 8: 1.25, 9: 1.08, 10: 1.00, 11: 0.97, 12: 1.15,
}


def _closed(day: dt.date) -> bool:
    return (day.month, day.day) in {(12, 25), (12, 26), (1, 1)}


def _next_business_day(day: dt.date) -> dt.date:
    day += dt.timedelta(days=1)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def month_range(start: dt.date, months: int) -> list[tuple[dt.date, dt.date]]:
    """[(first_day, last_day)] for each month of the window."""
    out = []
    y, m = start.year, start.month
    for _ in range(months):
        first = dt.date(y, m, 1)
        y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((first, dt.date(y2, m2, 1) - dt.timedelta(days=1)))
        y, m = y2, m2
    return out


def _month_end(year: int, month: int) -> dt.date:
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    return dt.date(y, m, 1) - dt.timedelta(days=1)


def quarter_ranges(cfg) -> list[tuple[dt.date, dt.date]]:
    """VAT quarters: consecutive 3-month blocks from the window start. The
    start month therefore IS the stagger (start June => quarters end
    Aug/Nov/Feb/May)."""
    months = month_range(cfg.start, cfg.months)
    return [(months[i][0], months[i + 2][1]) for i in range(0, cfg.months - 2, 3)]


def financial_years(cfg) -> list[tuple[dt.date, dt.date]]:
    """Every full financial year (ending in cfg.fye_month) inside the
    window. The window need not start on an FY boundary; partial years get
    no statutory accounts — exactly like a real data room."""
    out = []
    fy_end = _month_end(cfg.start.year, cfg.fye_month)
    while fy_end <= cfg.end:
        if cfg.fye_month == 12:
            fy_start = dt.date(fy_end.year, 1, 1)
        else:
            fy_start = dt.date(fy_end.year - 1, cfg.fye_month + 1, 1)
        if fy_start >= cfg.start:
            out.append((fy_start, fy_end))
        fy_end = _month_end(fy_end.year + 1, cfg.fye_month)
    return out


def ct_slices(cfg) -> list[tuple[dt.date, dt.date]]:
    """In-window slice of every financial year ENDING inside the window.

    When the window starts mid-FY the first slice is a stub: corporation
    tax is charged on its in-window profit only — the pre-window share of
    that FY is part of cfg.opening_ct_liability. With a window aligned to
    FY boundaries (the default config) the slices are exactly the full FYs.
    """
    out = []
    fye = _month_end(cfg.start.year, cfg.fye_month)
    if fye < cfg.start:
        fye = _month_end(cfg.start.year + 1, cfg.fye_month)
    while fye <= cfg.end:
        if cfg.fye_month == 12:
            fy_start = dt.date(fye.year, 1, 1)
        else:
            fy_start = dt.date(fye.year - 1, cfg.fye_month + 1, 1)
        out.append((max(cfg.start, fy_start), fye))
        fye = _month_end(fye.year + 1, cfg.fye_month)
    return out


def ct_due_date(fy_end: dt.date) -> dt.date:
    """Corporation tax is due 9 months + 1 day after the FYE. FYEs are
    month-ends, so that's the first day of the month 10 months on
    (31 Mar -> 1 Jan; 30 Sep -> 1 Jul)."""
    y, m = fy_end.year, fy_end.month + 10
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return dt.date(y, m, 1)


# Suppliers ----------------------------------------------------------------


@dataclass(frozen=True)
class SupplierSpec:
    name: str
    kind: str  # "cogs" (scales with takings) or "overhead" (fixed monthly)
    amount: float  # share of gross takings, or monthly pence
    vat_rate: float  # input VAT rate embedded in the payment
    cadence: str  # "weekly" or "monthly"


SUPPLIERS = (
    SupplierSpec("Shrewsbury Coffee Roasters", "cogs", 0.105, 0.0, "weekly"),
    SupplierSpec("Harlescott Food Wholesale", "cogs", 0.125, 0.0, "weekly"),
    SupplierSpec("Wenlock Dairy Ltd", "cogs", 0.055, 0.0, "weekly"),
    SupplierSpec("Severn Valley Bakery", "cogs", 0.045, 0.0, "weekly"),
    SupplierSpec("EDF ENERGY", "overhead", 645_00, 0.20, "monthly"),
    SupplierSpec("SEVERN TRENT WATER", "overhead", 155_00, 0.0, "monthly"),
    SupplierSpec("VEOLIA WASTE", "overhead", 185_00, 0.20, "monthly"),
    SupplierSpec("AXA INSURANCE", "overhead", 128_00, 0.0, "monthly"),
    SupplierSpec("BT BUSINESS", "overhead", 62_00, 0.20, "monthly"),
    SupplierSpec("MISC REPAIRS & SUNDRIES", "overhead", 210_00, 0.20, "monthly"),
)

COGS_SUPPLIERS = frozenset(s.name for s in SUPPLIERS if s.kind == "cogs")


# Payroll ------------------------------------------------------------------

PERSONAL_ALLOWANCE_M = 1_047_50  # £12,570 / 12, pence
EE_NI_THRESHOLD_M = 1_048_00
ER_NI_THRESHOLD_M = 758_00


def paye_breakdown(gross: int) -> tuple[int, int, int]:
    """(income_tax, employee_ni, employer_ni) per month, pence. Simplified UK bands."""
    tax = max(0, round((gross - PERSONAL_ALLOWANCE_M) * 0.20))
    ee_ni = max(0, round((gross - EE_NI_THRESHOLD_M) * 0.08))
    er_ni = max(0, round((gross - ER_NI_THRESHOLD_M) * 0.138))
    return tax, ee_ni, er_ni


def monthly_paye_bill(cfg: CafeConfig) -> int:
    """Total PAYE + EE NI + ER NI remitted to HMRC per month (constant roster)."""
    total = 0
    for emp in cfg.employees:
        tax, ee_ni, er_ni = paye_breakdown(emp.monthly_gross)
        total += tax + ee_ni + er_ni
    return total


# Loan ---------------------------------------------------------------------


def amortization_schedule(principal: int, annual_rate: float, term_months: int,
                          start: dt.date) -> list[tuple[dt.date, int, int, int]]:
    """[(payment_date, payment, interest, balance_after)] — pence, monthly."""
    r = annual_rate / 12
    payment = round(principal * r / (1 - (1 + r) ** -term_months))
    balance = principal
    rows = []
    y, m, day = start.year, start.month, min(start.day, 28)
    for i in range(term_months):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        interest = round(balance * r)
        pay = payment if i < term_months - 1 else balance + interest
        balance = balance - (pay - interest)
        rows.append((dt.date(y, m, day), pay, interest, balance))
    return rows


def loan_balance_at(cfg: CafeConfig, at: dt.date) -> int:
    """Outstanding principal after the last payment on or before `at`."""
    balance = cfg.loan.principal
    for pay_date, _pay, _int, bal in amortization_schedule(
            cfg.loan.principal, cfg.loan.annual_rate, cfg.loan.term_months, cfg.loan.start):
        if pay_date <= at:
            balance = bal
    return balance


# Generator ----------------------------------------------------------------


def generate_ledger(config: CafeConfig | None = None) -> Ledger:
    cfg = config or CafeConfig()
    rng = random.Random(cfg.seed)
    txns: list[Transaction] = []

    start, end = cfg.start, cfg.end

    # --- Daily sales, card settlements, weekly cash banking ---------------
    pending_card: list[tuple[dt.date, int]] = []  # (settlement_date, net_amount)
    cash_on_hand = 0
    day = start
    while day <= end:
        if not _closed(day):
            factor = WEEKDAY_FACTOR[day.weekday()] * MONTH_FACTOR[day.month]
            noise = rng.uniform(0.88, 1.12)
            gross = round(cfg.base_daily_takings * factor * noise)
            card_share = min(0.95, max(0.55, rng.gauss(cfg.card_share, 0.04)))
            card_gross = round(gross * card_share)
            cash_gross = gross - card_gross
            std_gross = round(gross * cfg.standard_rated_share)
            output_vat = round(std_gross * 20 / 120)
            txns.append(Transaction(
                date=day, type=TxnType.SALE, description="Daily till takings",
                amount=gross, card_gross=card_gross, cash_gross=cash_gross,
                vat=output_vat,
            ))
            fee = round(card_gross * cfg.card_fee_rate)
            pending_card.append((_next_business_day(day), card_gross - fee))
            cash_on_hand += cash_gross

        # Card settlements due today (processor batches by business day)
        due = [amt for (d, amt) in pending_card if d == day]
        if due:
            txns.append(Transaction(
                date=day, type=TxnType.CARD_SETTLEMENT,
                description=cfg.processor_name, amount=sum(due),
                counterparty="SumUp Payments Ltd",
            ))
            pending_card = [(d, a) for (d, a) in pending_card if d != day]

        # Weekly cash banking on Tuesdays
        if day.weekday() == 1 and cash_on_hand > 0:
            txns.append(Transaction(
                date=day, type=TxnType.CASH_DEPOSIT,
                description="CASH & CHEQUES PAID IN", amount=cash_on_hand,
                counterparty="Branch counter",
            ))
            cash_on_hand = 0
        day += dt.timedelta(days=1)

    # Flush trailing card settlements / cash so period totals reconcile
    # exactly (they land within days of period end).
    for d, amt in sorted(pending_card):
        txns.append(Transaction(
            date=min(d, end), type=TxnType.CARD_SETTLEMENT,
            description=cfg.processor_name, amount=amt,
            counterparty="SumUp Payments Ltd",
        ))
    if cash_on_hand:
        txns.append(Transaction(
            date=end, type=TxnType.CASH_DEPOSIT,
            description="CASH & CHEQUES PAID IN", amount=cash_on_hand,
            counterparty="Branch counter",
        ))

    months = month_range(start, cfg.months)
    sales_by_month = {
        first: sum(t.amount for t in txns
                   if t.type == TxnType.SALE and first <= t.date <= last)
        for first, last in months
    }

    # --- Suppliers ---------------------------------------------------------
    for first, _last in months:
        month_gross = sales_by_month[first]
        for sup in SUPPLIERS:
            if sup.kind == "cogs":
                total = round(month_gross * sup.amount * rng.uniform(0.93, 1.07))
            else:
                total = round(sup.amount * rng.uniform(0.92, 1.08))
            if sup.cadence == "weekly":
                per = total // 4
                for i, dom in enumerate((5, 12, 19, 26)):
                    amt = per if i < 3 else total - 3 * per
                    txns.append(Transaction(
                        date=dt.date(first.year, first.month, dom),
                        type=TxnType.SUPPLIER_PAYMENT, description=sup.name.upper(),
                        amount=amt, counterparty=sup.name,
                        vat=round(amt * sup.vat_rate / (1 + sup.vat_rate)),
                    ))
            else:
                txns.append(Transaction(
                    date=dt.date(first.year, first.month, 15),
                    type=TxnType.SUPPLIER_PAYMENT, description=sup.name.upper(),
                    amount=total, counterparty=sup.name,
                    vat=round(total * sup.vat_rate / (1 + sup.vat_rate)),
                ))

    # --- Payroll -----------------------------------------------------------
    paye_bill = monthly_paye_bill(cfg)
    for first, last in months:
        for emp in cfg.employees:
            tax, ee_ni, _er_ni = paye_breakdown(emp.monthly_gross)
            net = emp.monthly_gross - tax - ee_ni
            txns.append(Transaction(
                date=last, type=TxnType.PAYROLL_NET,
                description=f"WAGES {emp.name.upper()}", amount=net,
                counterparty=emp.name,
            ))
        # PAYE/NI for this month remitted on the 22nd of the following month
        ny, nm = (first.year + 1, 1) if first.month == 12 else (first.year, first.month + 1)
        paye_date = dt.date(ny, nm, 22)
        if paye_date <= end:
            txns.append(Transaction(
                date=paye_date, type=TxnType.HMRC_PAYE,
                description="HMRC PAYE/NI", amount=paye_bill,
                counterparty="HM Revenue & Customs",
            ))
    # PAYE for the month before the window (opening liability), paid on the 22nd
    txns.append(Transaction(
        date=dt.date(start.year, start.month, 22), type=TxnType.HMRC_PAYE,
        description="HMRC PAYE/NI", amount=paye_bill,
        counterparty="HM Revenue & Customs",
    ))

    # --- Rent ---------------------------------------------------------------
    monthly_rent = round(cfg.lease.annual_rent / 12)
    for first, _ in months:
        txns.append(Transaction(
            date=first, type=TxnType.RENT,
            description=f"RENT {cfg.lease.landlord.upper()}", amount=monthly_rent,
            counterparty=cfg.lease.landlord,
        ))

    # --- VAT payments (quarterly, due ~1 month + 7 days after quarter end) ---
    quarters = quarter_ranges(cfg)
    for qstart, qend in quarters:
        q_txns = [t for t in txns if qstart <= t.date <= qend]
        output_vat = sum(t.vat for t in q_txns if t.type == TxnType.SALE)
        input_vat = sum(t.vat for t in q_txns if t.type == TxnType.SUPPLIER_PAYMENT)
        due = qend + dt.timedelta(days=38)
        if due <= end:
            txns.append(Transaction(
                date=due, type=TxnType.VAT_PAYMENT,
                description="HMRC VAT", amount=output_vat - input_vat,
                counterparty="HM Revenue & Customs",
            ))
    # VAT for the quarter before the window (opening liability)
    txns.append(Transaction(
        date=cfg.start + dt.timedelta(days=37), type=TxnType.VAT_PAYMENT,
        description="HMRC VAT", amount=cfg.opening_vat_liability,
        counterparty="HM Revenue & Customs",
    ))

    # --- Loan repayments -----------------------------------------------------
    for pay_date, pay, interest, _bal in amortization_schedule(
            cfg.loan.principal, cfg.loan.annual_rate, cfg.loan.term_months, cfg.loan.start):
        if start <= pay_date <= end:
            txns.append(Transaction(
                date=pay_date, type=TxnType.LOAN_REPAYMENT,
                description=cfg.loan.lender.upper(), amount=pay,
                counterparty=cfg.loan.lender, interest=interest,
            ))

    # --- Dividends (quarterly) ------------------------------------------------
    for qstart, _qend in quarters:
        txns.append(Transaction(
            date=dt.date(qstart.year, qstart.month, 28), type=TxnType.DIVIDEND,
            description="DIVIDEND M HOLT", amount=cfg.dividend_quarterly,
            counterparty="Margaret Holt",
        ))

    # --- Corporation tax --------------------------------------------------------
    # Pre-window FYE liability, paid at its statutory due date (FYE + 9
    # months + 1 day) when that falls inside the window.
    prev_fye = _month_end(start.year, cfg.fye_month)
    if prev_fye >= start:
        prev_fye = _month_end(start.year - 1, cfg.fye_month)
    opening_ct_due = ct_due_date(prev_fye)
    if start <= opening_ct_due <= end:
        txns.append(Transaction(
            date=opening_ct_due, type=TxnType.CORPORATION_TAX,
            description="HMRC CORPORATION TAX", amount=cfg.opening_ct_liability,
            counterparty="HM Revenue & Customs",
        ))
    # Each in-window CT slice's liability, paid at its due date if still in
    # window. Charge = rate × slice profit before tax, computed from the
    # rows above (CT payments themselves don't affect PBT).
    from diligence.ledger.aggregates import profit_before_tax

    for slice_start, slice_end in ct_slices(cfg):
        due = ct_due_date(slice_end)
        if due > end:
            continue
        pbt = profit_before_tax(txns, cfg, slice_start, slice_end)
        txns.append(Transaction(
            date=due, type=TxnType.CORPORATION_TAX,
            description="HMRC CORPORATION TAX",
            amount=max(0, round(pbt * cfg.corporation_tax_rate)),
            counterparty="HM Revenue & Customs",
        ))

    txns.sort(key=lambda t: (t.date, t.type, t.description))
    return Ledger(config=cfg, transactions=txns)
