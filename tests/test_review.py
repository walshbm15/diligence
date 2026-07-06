"""Human verification queue tests (issue #22)."""

import datetime as dt

import pytest

from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD, Fact, FactType
from diligence.review import resolve_fact


@pytest.fixture()
def conn():
    psycopg = pytest.importorskip("psycopg")
    from diligence.facts import connect, init_db

    try:
        c = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    init_db(c)
    yield c
    c.execute("DELETE FROM fact WHERE dataroom = 'review_test'")
    c.commit()
    c.close()


@pytest.fixture()
def quarantined(conn):
    from diligence.facts.db import clear_dataroom, insert_facts

    clear_dataroom(conn, "review_test")
    facts = [
        Fact(dataroom="review_test", tier="clean", doc_type="vat_return",
             fact_type=FactType.VAT_BOX6, source_doc="vat_return_2024-06.pdf",
             page=1, confidence=0.55, value_pence=98_915_00,
             period_start=dt.date(2024, 4, 1), period_end=dt.date(2024, 6, 30)),
        Fact(dataroom="review_test", tier="clean", doc_type="bank_statement",
             fact_type=FactType.BANK_TXN, source_doc="bank_statement_2024-07.pdf",
             page=2, confidence=0.4, value_pence=1_234_00,
             attrs={"description": "SUMUP PAYOUTS", "direction": "in"}),
        Fact(dataroom="review_test", tier="clean", doc_type="statutory_accounts",
             fact_type=FactType.STAT_TURNOVER,
             source_doc="statutory_accounts_fye2025.pdf",
             page=2, confidence=0.0, value_pence=0),
    ]
    insert_facts(conn, facts)
    from diligence.facts.db import facts_needing_review

    return facts_needing_review(conn, "review_test", "clean",
                                CONFIDENCE_REVIEW_THRESHOLD)


def _queue(conn):
    from diligence.facts.db import facts_needing_review

    return facts_needing_review(conn, "review_test", "clean",
                                CONFIDENCE_REVIEW_THRESHOLD)


def test_accept_promotes_machine_value(conn, quarantined):
    from diligence.facts.db import fetch_facts

    row = next(r for r in quarantined if r["fact_type"] == FactType.VAT_BOX6)
    new_id = resolve_fact(conn, row, "accept")
    assert new_id is not None

    confident = fetch_facts(conn, "review_test", "clean",
                            min_confidence=CONFIDENCE_REVIEW_THRESHOLD)
    promoted = [r for r in confident if r["fact_type"] == FactType.VAT_BOX6]
    assert len(promoted) == 1
    assert promoted[0]["value_pence"] == 98_915_00
    assert promoted[0]["extractor"] == "human"
    assert promoted[0]["attrs"]["original_fact_id"] == row["id"]
    # provenance preserved
    assert promoted[0]["source_doc"] == row["source_doc"]
    assert promoted[0]["page"] == row["page"]


def test_correct_inserts_reviewer_value(conn, quarantined):
    row = next(r for r in quarantined if r["fact_type"] == FactType.BANK_TXN)
    resolve_fact(conn, row, "correct", corrected_pence=1_243_00)
    from diligence.facts.db import fetch_facts

    confident = fetch_facts(conn, "review_test", "clean",
                            min_confidence=CONFIDENCE_REVIEW_THRESHOLD)
    txn = [r for r in confident if r["fact_type"] == FactType.BANK_TXN][0]
    assert txn["value_pence"] == 1_243_00
    assert txn["attrs"]["description"] == "SUMUP PAYOUTS"  # attrs carried over


def test_unreadable_resolves_without_new_fact(conn, quarantined):
    from diligence.facts.db import fetch_facts

    row = next(r for r in quarantined
               if r["fact_type"] == FactType.STAT_TURNOVER)
    assert resolve_fact(conn, row, "unreadable") is None
    confident = fetch_facts(conn, "review_test", "clean",
                            min_confidence=CONFIDENCE_REVIEW_THRESHOLD)
    assert not [r for r in confident
                if r["fact_type"] == FactType.STAT_TURNOVER]


def test_queue_shrinks_and_originals_are_audit_trail(conn, quarantined):
    assert len(_queue(conn)) == 3
    for row in quarantined:
        resolve_fact(conn, row, "unreadable")
    assert _queue(conn) == []
    # originals still exist, marked reviewed
    rows = conn.execute(
        "SELECT attrs FROM fact WHERE dataroom='review_test' "
        "AND extractor != 'human'").fetchall()
    assert len(rows) == 3
    assert all(r["attrs"].get("reviewed") for r in rows)


def test_invalid_actions_rejected(conn, quarantined):
    with pytest.raises(ValueError):
        resolve_fact(conn, quarantined[0], "approve")
    with pytest.raises(ValueError):
        resolve_fact(conn, quarantined[0], "correct")  # no value
