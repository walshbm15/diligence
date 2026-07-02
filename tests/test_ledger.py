"""Internal-consistency invariants for the synthetic ledger.

These tests are the proof of Week 1's core property: the data room is
internally consistent by construction, so every discrepancy later found by
the pipeline must have been planted by the mutation engine.
"""

import datetime as dt

from diligence.ledger import generate_ledger
from diligence.ledger.aggregates import (
    balance_sheet,
    bank_lines,
    ct_charge,
    financial_years,
    monthly_pnls,
    vat_returns,
)
from diligence.ledger.generator import month_range
from diligence.ledger.models import TxnType


def _ledger():
    return generate_ledger()


def test_deterministic_for_same_seed():
    a, b = generate_ledger(), generate_ledger()
    assert a.transactions == b.transactions


def test_covers_24_months_of_trading():
    led = _ledger()
    months_with_sales = {
        (t.date.year, t.date.month)
        for t in led.of_type(TxnType.SALE)
    }
    assert len(months_with_sales) == 24


def test_sale_split_sums_to_gross():
    led = _ledger()
    for t in led.of_type(TxnType.SALE):
        assert t.card_gross + t.cash_gross == t.amount


def test_card_settlements_reconcile_to_card_takings_net_of_fees():
    led = _ledger()
    cfg = led.config
    expected = sum(t.card_gross - round(t.card_gross * cfg.card_fee_rate)
                   for t in led.of_type(TxnType.SALE))
    settled = sum(t.amount for t in led.of_type(TxnType.CARD_SETTLEMENT))
    assert settled == expected


def test_cash_deposits_reconcile_to_cash_takings():
    led = _ledger()
    taken = sum(t.cash_gross for t in led.of_type(TxnType.SALE))
    banked = sum(t.amount for t in led.of_type(TxnType.CASH_DEPOSIT))
    assert banked == taken


def test_vat_box6_equals_pnl_revenue_per_quarter():
    led = _ledger()
    pnls = monthly_pnls(led)
    for i, ret in enumerate(vat_returns(led)):
        quarter_revenue = sum(p.revenue for p in pnls[i * 3:i * 3 + 3])
        assert ret.box6 == quarter_revenue


def test_vat_payments_match_box5_of_prior_quarter():
    led = _ledger()
    returns = vat_returns(led)
    payments = [t for t in led.of_type(TxnType.VAT_PAYMENT)]
    # First payment is the pre-window quarter; the rest map 1:1 to returns
    # whose due date fell inside the window (last return unpaid at window end).
    in_window = payments[1:]
    assert len(in_window) == len(returns) - 1
    for ret, pay in zip(returns, in_window, strict=False):
        assert pay.amount == ret.box5


def test_corporation_tax_payment_matches_fy1_charge():
    led = _ledger()
    (fy1_start, fy1_end), _fy2 = financial_years(led.config)
    expected = ct_charge(led, fy1_start, fy1_end)
    ct_payments = led.of_type(TxnType.CORPORATION_TAX)
    fy1_payment = [t for t in ct_payments
                   if t.date == dt.date(led.config.start.year + 2, 1, 1)]
    assert len(fy1_payment) == 1
    assert fy1_payment[0].amount == expected


def test_balance_sheet_ties_exactly_at_both_year_ends():
    led = _ledger()
    for _fy_start, fy_end in financial_years(led.config):
        bs = balance_sheet(led, fy_end)
        assert bs.net_assets == bs.capital_and_reserves, (
            f"balance sheet off by {bs.net_assets - bs.capital_and_reserves}p "
            f"at {fy_end}"
        )


def test_bank_balance_stays_positive():
    led = _ledger()
    assert min(line.balance for line in bank_lines(led)) > 0


def test_seasonality_summer_beats_winter():
    led = _ledger()
    pnls = monthly_pnls(led)
    by_month = {p.period_start: p.revenue for p in pnls}
    months = month_range(led.config.start, led.config.months)
    aug = [by_month[f] for f, _l in months if f.month == 8]
    feb = [by_month[f] for f, _l in months if f.month == 2]
    assert min(aug) > max(feb)


def test_profit_margin_is_realistic_for_a_cafe():
    led = _ledger()
    for fy_start, fy_end in financial_years(led.config):
        from diligence.ledger.aggregates import pnl
        p = pnl(led.transactions, led.config, fy_start, fy_end)
        margin = p.profit_before_tax / p.revenue
        assert 0.03 < margin < 0.20, f"FY margin {margin:.1%} implausible"
