"""Mutation engine tests.

Week 1 exit criterion: a data room where every answer is known. Each
mutation must (a) actually change the documents, (b) log ground truth the
eval harness can score against, and (c) leave the documents individually
plausible (balance sheets still tie, bank balances still reconcile).
"""

import datetime as dt

import pytest

from diligence.dataroom.spec import build_spec
from diligence.ledger import generate_ledger
from diligence.mutations import DEFAULT_MUTATIONS, apply_mutations


@pytest.fixture()
def clean_spec():
    return build_spec(generate_ledger())


@pytest.fixture()
def mutated():
    spec = build_spec(generate_ledger())
    records = apply_mutations(spec, DEFAULT_MUTATIONS)
    return spec, records


def test_ten_mutations_logged_with_taxonomy(mutated):
    spec, records = mutated
    assert len(records) == 10
    assert len(spec.mutations) == 10
    for rec in records:
        assert rec.check_id.startswith(("T1.", "T2.", "T3."))
        assert rec.severity in ("red", "amber")
        assert rec.affected_documents
    # 8-10 must be catchable by POC-scope checks (plan: >=8/10 caught)
    catchable = [r for r in records if r.catchable_in_poc]
    assert len(catchable) >= 8


def test_mgmt_revenue_inflated_vs_clean(clean_spec, mutated):
    spec, _ = mutated
    clean_fy2 = sum(m.revenue for m in clean_spec.management_pnl.months[12:])
    mutated_fy2 = sum(m.revenue for m in spec.management_pnl.months[12:])
    assert mutated_fy2 > clean_fy2 * 1.10
    # FY1 untouched
    assert (sum(m.revenue for m in spec.management_pnl.months[:12])
            == sum(m.revenue for m in clean_spec.management_pnl.months[:12]))


def test_vat_q3_understated_and_internally_consistent(clean_spec, mutated):
    spec, _ = mutated
    ret = spec.vat_returns[2]
    clean_ret = clean_spec.vat_returns[2]
    assert ret.box6 < clean_ret.box6 * 0.95
    # The mutated return still adds up internally (fraud, not typos)
    assert ret.box3 == ret.box1 + ret.box2
    assert ret.box5 == ret.box3 - ret.box4


def test_loan_hidden_but_balance_sheets_still_tie(mutated):
    spec, _ = mutated
    for acc in spec.statutory_accounts:
        assert acc.loan_disclosure is None
        b = acc.balance
        assert b.note_loan_within_year == 0
        assert b.note_loan_after_year == 0
        net = (b.fixed_assets + b.stock + b.debtors + b.cash
               - b.creditors_within_year - b.creditors_after_year)
        assert net == b.share_capital + b.retained_earnings
    borrow_claim = next(c for c in spec.seller_claims
                        if c.metric == "total_borrowings")
    assert borrow_claim.value_gbp == 0


def test_loan_repayments_still_visible_in_bank(mutated):
    spec, _ = mutated
    fc_lines = [line for stmt in spec.bank_statements for line in stmt.lines
                if "FUNDING CIRCLE" in line.description]
    assert len(fc_lines) == 24


def test_lease_break_moved_to_month_nine(mutated):
    spec, _ = mutated
    assert spec.lease.break_date == dt.date(2027, 1, 15)
    assert spec.lease.break_notice_months == 3


def test_stat_fy1_turnover_below_mgmt(mutated):
    spec, _ = mutated
    stat = spec.statutory_accounts[0]
    mgmt_fy1 = sum(m.revenue for m in spec.management_pnl.months[:12])
    assert stat.turnover < mgmt_fy1 * 0.95
    b = stat.balance
    net = (b.fixed_assets + b.stock + b.debtors + b.cash
           - b.creditors_within_year - b.creditors_after_year)
    assert net == b.share_capital + b.retained_earnings


def test_claims_mutated(mutated):
    spec, _ = mutated
    aug = next(c for c in spec.seller_claims if c.metric == "monthly_revenue_net")
    card = next(c for c in spec.seller_claims if c.metric == "card_share")
    assert aug.value_gbp == 52_000_00
    assert card.value_ratio == 0.60


def test_bank_running_balances_reconcile_after_mutations(mutated):
    spec, _ = mutated
    balance = spec.bank_statements[0].opening_balance
    for stmt in spec.bank_statements:
        assert stmt.opening_balance == balance
        for line in stmt.lines:
            balance += line.paid_in - line.paid_out
            assert line.balance == balance
        assert stmt.closing_balance == balance


def test_spouse_wages_and_personal_deposit_planted(mutated):
    spec, _ = mutated
    spouse = [line for stmt in spec.bank_statements for line in stmt.lines
              if line.description == "WAGES DEREK HOLT"]
    assert len(spouse) == 24
    personal = [line for stmt in spec.bank_statements for line in stmt.lines
                if line.description == "FASTER PAYMENT M HOLT PERSONAL"]
    assert len(personal) == 1 and personal[0].paid_in == 15_000_00


def test_vat_payment_short_by_2400(clean_spec, mutated):
    spec, _ = mutated

    def hmrc_nov(s):
        stmt = next(x for x in s.bank_statements
                    if x.period_start == dt.date(2024, 11, 1))
        return next(ln for ln in stmt.lines if ln.description == "HMRC VAT")

    assert hmrc_nov(clean_spec).paid_out - hmrc_nov(spec).paid_out == 2_400_00


def test_clean_room_has_no_mutations_and_truthful_claims(clean_spec):
    assert clean_spec.mutations == []
    aug = next(c for c in clean_spec.seller_claims
               if c.metric == "monthly_revenue_net")
    actual = next(m for m in clean_spec.management_pnl.months
                  if m.period_start == aug.period_start)
    # truthful claim rounded to nearest £500
    assert abs(aug.value_gbp - actual.revenue) <= 250_00
