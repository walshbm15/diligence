"""Check-level tests: catch every catchable mutation, stay silent on clean.

Facts come from the data room spec's ground truth (perfect extraction), so
these tests validate check logic in isolation from extraction quality.
"""

import dataclasses
import json

import pytest

from diligence.checks import CheckContext, FactIndex, run_all
from diligence.dataroom.build import companies_house_fixture
from diligence.dataroom.spec import build_spec
from diligence.evals.ground_truth import expected_facts
from diligence.external import CompaniesHouseFixture
from diligence.ledger import generate_ledger
from diligence.mutations import DEFAULT_MUTATIONS, apply_mutations


def _context(mutated: bool) -> CheckContext:
    ledger = generate_ledger()
    spec = build_spec(ledger)
    if mutated:
        apply_mutations(spec, DEFAULT_MUTATIONS)
    facts = [dataclasses.replace(f, tier="clean")
             for f in expected_facts(spec, dataroom="test")]
    claims = json.loads(json.dumps(
        [dataclasses.asdict(c) for c in spec.seller_claims], default=str))
    return CheckContext(
        facts=FactIndex(facts),
        claims=claims,
        companies_house=CompaniesHouseFixture(
            companies_house_fixture(ledger.config)),
        company_number=ledger.config.company_number,
    )


@pytest.fixture(scope="module")
def clean_findings():
    return run_all(_context(mutated=False))


@pytest.fixture(scope="module")
def mutated_findings():
    return run_all(_context(mutated=True))


def test_clean_room_produces_no_red_or_amber(clean_findings):
    alarms = [f for f in clean_findings if f.severity in ("red", "amber")]
    assert alarms == [], [f"{f.check_id}: {f.finding}" for f in alarms]


def test_clean_room_confirms_disclosed_charge(clean_findings):
    infos = [f for f in clean_findings if f.check_id == "T3.CHARGES"]
    assert len(infos) == 1 and infos[0].severity == "info"


def _by_check(findings, check_id, severity=None):
    return [f for f in findings if f.check_id == check_id
            and (severity is None or f.severity == severity)]


def test_vat_triangle_catches_inflated_pnl_and_understated_box6(mutated_findings):
    reds = _by_check(mutated_findings, "T1.VAT_TRIANGLE", "red")
    quarters = {f.period_end for f in reds}
    import datetime as dt

    # M02: Q3 2024 Box 6 understated
    assert dt.date(2024, 12, 31) in quarters
    # M01: FY2 P&L inflated — all four FY2 quarters diverge
    assert dt.date(2025, 6, 30) in quarters
    assert dt.date(2026, 3, 31) in quarters


def test_vat_triangle_catches_short_payment_and_personal_deposit(mutated_findings):
    import datetime as dt

    ambers = _by_check(mutated_findings, "T1.VAT_TRIANGLE", "amber")
    assert any(f.period_end == dt.date(2024, 9, 30)
               and "short" in f.finding for f in ambers)  # M08
    assert any(f.details.get("amount_pence") == 15_000_00
               for f in ambers)  # M10 personal deposit


def test_card_recon_catches_cash_addback_claim(mutated_findings):
    reds = _by_check(mutated_findings, "T1.CARD_RECON", "red")
    assert len(reds) == 1
    assert reds[0].details["claimed_share"] == 0.60


def test_stat_vs_mgmt_catches_both_fy_gaps(mutated_findings):
    reds = _by_check(mutated_findings, "T1.STAT_VS_MGMT", "red")
    assert len(reds) == 2  # M05 (FY1 stat understated) + M01 (FY2 mgmt inflated)


def test_claim_ledger_catches_inflated_august(mutated_findings):
    reds = _by_check(mutated_findings, "T1.CLAIM_LEDGER", "red")
    assert any(f.details.get("claimed") == 52_000_00 for f in reds)


def test_charges_catches_hidden_loan(mutated_findings):
    reds = _by_check(mutated_findings, "T3.CHARGES", "red")
    assert len(reds) == 1
    f = reds[0]
    assert f.details["lender"] == "Funding Circle Ltd"
    assert any(e.doc_id == "companies_house:charges" for e in f.evidence)
    assert any(e.doc_id.startswith("bank_statement") for e in f.evidence)


def test_lease_catches_month_nine_break(mutated_findings):
    reds = _by_check(mutated_findings, "T3.LEASE", "red")
    assert len(reds) == 1
    assert reds[0].details["months_to_break"] < 12


def test_every_finding_has_citations(mutated_findings, clean_findings):
    for f in mutated_findings + clean_findings:
        assert f.evidence
        for e in f.evidence:
            assert e.doc_id and e.page >= 1
