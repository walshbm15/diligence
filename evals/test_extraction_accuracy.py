"""Extraction accuracy eval — stratified by document quality tier.

Deterministic scorer tests always run (CI). The live eval extracts the
synthetic data room through the Claude API and asserts the Week 2 exit
criterion: >=95% field-level accuracy on clean documents, per doc type.
Watch the scanned tier against the <85% kill criterion (docs/02).

Run live:  pytest evals/test_extraction_accuracy.py -s
Needs:     ANTHROPIC_API_KEY (.env), Postgres up, data_rooms/ generated.
"""

import dataclasses
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from diligence.dataroom.spec import build_spec
from diligence.evals.ground_truth import expected_facts
from diligence.evals.scoring import score_extraction
from diligence.facts.model import FactType
from diligence.ledger import generate_ledger

load_dotenv()

ROOM = Path("data_rooms/copper_kettle_clean")
CLEAN_EXIT = 0.95
SCANNED_KILL = 0.85


@pytest.fixture(scope="module")
def spec():
    return build_spec(generate_ledger())


@pytest.fixture(scope="module")
def expected(spec):
    return expected_facts(spec, dataroom="copper_kettle_clean")


def test_ground_truth_covers_all_doc_types(expected):
    doc_types = {f.doc_type for f in expected}
    assert doc_types == {"statutory_accounts", "management_pnl",
                         "bank_statement", "vat_return", "lease"}
    # 24 months x 9 mgmt lines, 8 quarters x 7 boxes, 2 FYs of accounts
    mgmt = [f for f in expected if f.doc_type == "management_pnl"]
    assert len(mgmt) == 24 * 9
    vat = [f for f in expected if f.doc_type == "vat_return"]
    assert len(vat) == 8 * 7


def test_perfect_extraction_scores_100(expected):
    extracted = [dataclasses.replace(f, tier="clean", extractor="fake")
                 for f in expected]
    report = score_extraction(expected, extracted, tier="clean")
    assert report.overall == 1.0
    for score in report.by_doc_type.values():
        assert score.accuracy == 1.0


def test_wrong_values_and_missing_facts_lower_accuracy(expected):
    extracted = [dataclasses.replace(f, tier="clean") for f in expected]
    # Corrupt one VAT box and drop one bank transaction
    for i, f in enumerate(extracted):
        if f.fact_type == FactType.VAT_BOX6:
            extracted[i] = dataclasses.replace(f, value_pence=f.value_pence + 100_00)
            break
    for i, f in enumerate(extracted):
        if f.fact_type == FactType.BANK_TXN:
            del extracted[i]
            break
    report = score_extraction(expected, extracted, tier="clean")
    assert report.by_doc_type["vat_return"].accuracy < 1.0
    assert report.by_doc_type["bank_statement"].accuracy < 1.0
    assert report.by_doc_type["vat_return"].mismatches
    assert "OVERALL" in report.table()


# --- Live eval (Claude API + Postgres + generated data room) ---------------

live = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — live extraction eval skipped")


@pytest.fixture(scope="module")
def conn():
    psycopg = pytest.importorskip("psycopg")
    from diligence.facts import connect, init_db

    try:
        c = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    init_db(c)
    yield c
    c.close()


@live
@pytest.mark.parametrize("tier", ["clean", "scanned", "photographed"])
def test_live_extraction_accuracy(tier, conn, expected):
    if not ROOM.exists():
        pytest.skip("data room missing — run `diligence generate`")
    from diligence.extraction.extractor import ClaudeExtractor
    from diligence.extraction.pipeline import extract_dataroom
    from diligence.facts.db import fetch_facts, row_to_fact

    extractor = ClaudeExtractor()
    # resume=True: re-runs only pay for documents that failed last time
    result = extract_dataroom(conn, extractor, ROOM, tier, resume=True)
    assert not result.failures, result.failures

    rows = fetch_facts(conn, ROOM.name, tier)
    extracted = [row_to_fact(r) for r in rows]
    report = score_extraction(expected, extracted, tier=tier)
    print(f"\n{report.table()}")
    print(f"API cost this tier: ~${extractor.usage.cost_usd:.2f}")
    for score in report.by_doc_type.values():
        for miss in score.mismatches[:5]:
            print(f"    MISS {miss}")

    if tier == "clean":
        for doc_type, score in report.by_doc_type.items():
            assert score.accuracy >= CLEAN_EXIT, (
                f"{doc_type} accuracy {score.accuracy:.1%} below the "
                f">= {CLEAN_EXIT:.0%} Week 2 exit criterion")
    elif tier == "scanned" and report.overall < SCANNED_KILL:
        print(f"WARNING: scanned accuracy {report.overall:.1%} is below the "
              f"{SCANNED_KILL:.0%} pre-committed kill criterion "
              f"(docs/02-stress-test.md)")
