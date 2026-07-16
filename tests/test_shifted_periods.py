"""Issue #26: the synthetic world must not smuggle period assumptions.

Real businesses have any FYE and any VAT stagger. Everything here runs the
ledger invariants, the spec, and the full check suite against a config with
a 30 September FYE, quarters ending Aug/Nov/Feb/May, and an 18-month window
(not a multiple of 12 — the window starts mid-financial-year).
"""

import datetime as dt

import pytest

from diligence.checks import CheckContext, FactIndex, run_all
from diligence.dataroom.spec import build_spec
from diligence.evals.ground_truth import expected_facts
from diligence.ledger import generate_ledger
from diligence.ledger.aggregates import (
    balance_sheet,
    bank_lines,
    financial_years,
    monthly_pnls,
    quarter_ranges,
    vat_returns,
)
from diligence.ledger.generator import ct_due_date
from diligence.ledger.models import CafeConfig, TxnType

SHIFTED = CafeConfig(start=dt.date(2024, 6, 1), months=18, fye_month=9)


@pytest.fixture(scope="module")
def ledger():
    return generate_ledger(SHIFTED)


@pytest.fixture(scope="module")
def spec(ledger):
    return build_spec(ledger)


# --- Period derivation ------------------------------------------------------


def test_quarters_follow_the_stagger():
    ends = [qend.month for _qstart, qend in quarter_ranges(SHIFTED)]
    assert ends == [8, 11, 2, 5, 8, 11]  # Aug/Nov/Feb/May cycle


def test_single_full_fy_inside_18_month_window():
    assert financial_years(SHIFTED) == [
        (dt.date(2024, 10, 1), dt.date(2025, 9, 30))]


def test_default_config_unchanged():
    """Backward compatibility: the original café world must be identical."""
    cfg = CafeConfig()
    assert financial_years(cfg) == [
        (dt.date(2024, 4, 1), dt.date(2025, 3, 31)),
        (dt.date(2025, 4, 1), dt.date(2026, 3, 31))]
    assert len(quarter_ranges(cfg)) == 8
    assert ct_due_date(dt.date(2025, 3, 31)) == dt.date(2026, 1, 1)


def test_config_validation():
    with pytest.raises(ValueError):
        CafeConfig(months=17)  # partial VAT quarter
    with pytest.raises(ValueError):
        CafeConfig(start=dt.date(2024, 4, 15))  # mid-month start
    with pytest.raises(ValueError):
        CafeConfig(fye_month=13)


# --- Ledger invariants on the shifted world ---------------------------------


def test_vat_box6_equals_pnl_revenue_per_quarter(ledger):
    pnls = monthly_pnls(ledger)
    for i, ret in enumerate(vat_returns(ledger)):
        assert ret.box6 == sum(p.revenue for p in pnls[i * 3:i * 3 + 3])


def test_vat_payments_match_box5(ledger):
    returns = vat_returns(ledger)
    payments = ledger.of_type(TxnType.VAT_PAYMENT)
    in_window = payments[1:]  # first is the pre-window opening liability
    assert len(in_window) == len(returns) - 1  # last return unpaid at end
    for ret, pay in zip(returns, in_window, strict=False):
        assert pay.amount == ret.box5


def test_ct_paid_at_statutory_due_dates(ledger):
    """Every CT payment lands at FYE + 9 months + 1 day, never 1 January:
    - pre-window FYE 30 Sep 2023 -> paid 1 Jul 2024
    - stub slice (Jun-Sep 2024, FYE 30 Sep 2024) -> paid 1 Jul 2025
    - full FY (FYE 30 Sep 2025) -> due 1 Jul 2026, after the window: unpaid.
    """
    from diligence.ledger.aggregates import ct_charge

    ct = ledger.of_type(TxnType.CORPORATION_TAX)
    assert [t.date for t in ct] == [dt.date(2024, 7, 1), dt.date(2025, 7, 1)]
    assert ct[0].amount == SHIFTED.opening_ct_liability
    stub = ct_charge(ledger, dt.date(2024, 6, 1), dt.date(2024, 9, 30))
    assert ct[1].amount == stub
    assert ct_due_date(dt.date(2023, 9, 30)) == dt.date(2024, 7, 1)


def test_balance_sheet_ties_exactly_at_shifted_fye(ledger):
    for _fy_start, fy_end in financial_years(ledger.config):
        bs = balance_sheet(ledger, fy_end)
        assert bs.net_assets == bs.capital_and_reserves, (
            f"off by {bs.net_assets - bs.capital_and_reserves}p at {fy_end}")


def test_bank_balance_stays_positive(ledger):
    assert min(line.balance for line in bank_lines(ledger)) > 0


# --- Spec + check suite on ground truth --------------------------------------


def test_spec_has_one_statutory_account_and_six_vat_returns(spec):
    assert [(a.fy_start, a.fy_end) for a in spec.statutory_accounts] == [
        (dt.date(2024, 10, 1), dt.date(2025, 9, 30))]
    assert len(spec.vat_returns) == 6


def test_clean_shifted_room_produces_zero_findings(spec):
    facts = expected_facts(spec, dataroom="shifted_clean")
    findings = run_all(CheckContext(facts=FactIndex(facts), claims=[]))
    assert findings == [], [f.finding for f in findings]


def test_sufficiency_expectations_derive_from_config(spec):
    """A complete 18-month room must score ~100, not be punished for not
    being the 24-month café default."""
    from diligence.report.sufficiency import assess

    facts = expected_facts(spec, dataroom="shifted_clean")
    fys = financial_years(SHIFTED)
    report = assess(FactIndex(facts),
                    expected_bank_months=SHIFTED.months,
                    expected_vat_quarters=SHIFTED.months // 3,
                    expected_fys=len(fys))
    assert report.score >= 95, [i.__dict__ for i in report.items]
    # And against the café default it must NOT score full — the FY count
    # differs, which is exactly why expectations have to be config-derived.
    stale = assess(FactIndex(facts))
    assert stale.score < report.score
