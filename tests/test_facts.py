"""Fact table tests: provenance enforcement + Postgres round-trip."""

import datetime as dt

import pytest

from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD, Fact, FactType


def _fact(**kw) -> Fact:
    base = dict(
        dataroom="test_room", tier="clean", doc_type="vat_return",
        fact_type=FactType.VAT_BOX6, source_doc="vat_return_2024-06.pdf",
        page=1, confidence=0.97, value_pence=98_915_00,
        period_start=dt.date(2024, 4, 1), period_end=dt.date(2024, 6, 30),
    )
    base.update(kw)
    return Fact(**base)


def test_fact_requires_provenance():
    with pytest.raises(ValueError):
        _fact(source_doc="")
    with pytest.raises(ValueError):
        _fact(page=0)
    with pytest.raises(ValueError):
        _fact(confidence=1.2)


def test_low_confidence_flags_review():
    assert _fact(confidence=CONFIDENCE_REVIEW_THRESHOLD - 0.01).needs_review
    assert not _fact(confidence=CONFIDENCE_REVIEW_THRESHOLD).needs_review


# --- Postgres round-trip -------------------------------------------------


@pytest.fixture(scope="module")
def conn():
    psycopg = pytest.importorskip("psycopg")
    from diligence.facts import connect, init_db

    try:
        c = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (docker compose up -d)")
    init_db(c)
    yield c
    c.execute("DELETE FROM fact WHERE dataroom = 'test_room'")
    c.commit()
    c.close()


def test_insert_and_fetch_roundtrip(conn):
    from diligence.facts.db import (
        clear_dataroom,
        facts_needing_review,
        fetch_facts,
        insert_facts,
        row_to_fact,
    )

    clear_dataroom(conn, "test_room")
    facts = [
        _fact(),
        _fact(fact_type=FactType.VAT_BOX1, value_pence=16_325_78,
              confidence=0.99),
        _fact(fact_type=FactType.LEASE_BREAK_DATE, doc_type="lease",
              source_doc="lease.pdf", page=3, value_pence=None,
              value_date=dt.date(2026, 9, 29), period_start=None,
              period_end=None, confidence=0.65,
              attrs={"notice_months": 6}),
        _fact(fact_type=FactType.BANK_TXN, doc_type="bank_statement",
              source_doc="bank_statement_2024-07.pdf", page=1,
              value_pence=-2_166_67, period_start=None, period_end=None,
              attrs={"description": "RENT BRIDGNORTH ESTATES LLP",
                     "direction": "out"},
              bbox=(10.0, 20.0, 300.0, 34.0)),
    ]
    assert insert_facts(conn, facts) == 4

    rows = fetch_facts(conn, "test_room", "clean")
    assert len(rows) == 4

    box6 = fetch_facts(conn, "test_room", "clean",
                       fact_type=FactType.VAT_BOX6)[0]
    f = row_to_fact(box6)
    assert f.value_pence == 98_915_00
    assert f.period_end == dt.date(2024, 6, 30)
    assert f.source_doc == "vat_return_2024-06.pdf"

    bank = fetch_facts(conn, "test_room", "clean",
                       fact_type=FactType.BANK_TXN)[0]
    f = row_to_fact(bank)
    assert f.attrs["description"] == "RENT BRIDGNORTH ESTATES LLP"
    assert f.bbox == (10.0, 20.0, 300.0, 34.0)

    review = facts_needing_review(conn, "test_room", "clean",
                                  CONFIDENCE_REVIEW_THRESHOLD)
    assert len(review) == 1
    assert review[0]["fact_type"] == FactType.LEASE_BREAK_DATE

    # High-confidence filter excludes the uncertain lease fact
    confident = fetch_facts(conn, "test_room", "clean",
                            min_confidence=CONFIDENCE_REVIEW_THRESHOLD)
    assert len(confident) == 3


def test_db_rejects_missing_provenance(conn):
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO fact (dataroom, tier, doc_type, fact_type, "
            "source_doc, page, confidence) "
            "VALUES ('test_room', 'clean', 'lease', 'x', '', 1, 0.9)")
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO fact (dataroom, tier, doc_type, fact_type, "
            "source_doc, page, confidence) "
            "VALUES ('test_room', 'clean', 'lease', 'x', 'lease.pdf', 0, 0.9)")
    conn.rollback()
