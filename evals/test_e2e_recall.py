"""End-to-end eval: red-flag recall + false positives + citation integrity.

Week 3 exit criteria (docs/04): >=8/10 planted discrepancies caught, ZERO
hallucinated findings, zero red/amber on the clean room. Runs fully
deterministically in CI on ground-truth facts (perfect extraction); the
same scoring applies to live-extracted facts once credentials exist.
"""

import dataclasses
import json

import pytest

from diligence.checks import CheckContext, FactIndex, run_all
from diligence.dataroom.build import companies_house_fixture
from diligence.dataroom.spec import build_spec
from diligence.evals.e2e import citation_violations, score_recall
from diligence.evals.ground_truth import expected_facts
from diligence.external import CompaniesHouseFixture
from diligence.ledger import generate_ledger
from diligence.mutations import DEFAULT_MUTATIONS, apply_mutations

EXIT_RECALL = 8  # of 10 planted mutations


def _room(mutated: bool):
    ledger = generate_ledger()
    spec = build_spec(ledger)
    log = []
    if mutated:
        records = apply_mutations(spec, DEFAULT_MUTATIONS)
        log = [dataclasses.asdict(r) for r in records]
        log = json.loads(json.dumps(log, default=str))
    facts = expected_facts(spec, dataroom="e2e")
    claims = json.loads(json.dumps(
        [dataclasses.asdict(c) for c in spec.seller_claims], default=str))
    ctx = CheckContext(
        facts=FactIndex(facts), claims=claims,
        companies_house=CompaniesHouseFixture(
            companies_house_fixture(ledger.config)),
        company_number=ledger.config.company_number)
    documents = {f.source_doc for f in facts}
    return run_all(ctx), log, documents


@pytest.fixture(scope="module")
def mutated_run():
    return _room(mutated=True)


@pytest.fixture(scope="module")
def clean_run():
    return _room(mutated=False)


def test_recall_meets_exit_criterion(mutated_run):
    findings, log, _docs = mutated_run
    report = score_recall(log, findings)
    print(f"\n{report.table()}")
    assert report.total == 10
    assert len(report.caught) >= EXIT_RECALL, report.table()
    # every miss must be an expected out-of-scope miss, not a silent failure
    assert report.missed_catchable == [], report.table()


def test_red_recall_is_total(mutated_run):
    findings, log, _docs = mutated_run
    report = score_recall(log, findings)
    caught_red, total_red = report.by_severity["red"]
    assert caught_red == total_red  # all deal-killers caught


def test_zero_false_positives_on_clean_room(clean_run):
    findings, _log, _docs = clean_run
    alarms = [f for f in findings if f.severity in ("red", "amber")]
    assert alarms == [], [f"{f.check_id}: {f.finding[:80]}" for f in alarms]


def test_zero_hallucinated_citations(mutated_run, clean_run):
    for findings, _log, documents in (mutated_run, clean_run):
        assert citation_violations(findings, documents) == []


def test_every_red_names_seller_action_and_warranty(mutated_run):
    findings, _log, _docs = mutated_run
    for f in findings:
        if f.severity == "red":
            assert len(f.ask_the_seller) > 20
            assert len(f.warranty_suggestion) > 20
