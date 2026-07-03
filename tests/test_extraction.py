"""Extraction pipeline tests using the FakeExtractor (no API, no network)."""

import datetime as dt

import pytest

from diligence.extraction.extractor import FakeExtractor
from diligence.extraction.facts_builder import build_facts, doc_type_for
from diligence.extraction.pipeline import extract_dataroom
from diligence.facts.model import FactType

VAT_JSON = {
    "period_start": "2024-04-01", "period_end": "2024-06-30", "page": 1,
    "box1": {"value": 16325.78, "confidence": 0.99},
    "box2": {"value": 0.0, "confidence": 0.99},
    "box3": {"value": 16325.78, "confidence": 0.99},
    "box4": {"value": 544.12, "confidence": 0.98},
    "box5": {"value": 15781.66, "confidence": 0.99},
    "box6": {"value": 98915.0, "confidence": 0.99},
    "box7": {"value": 41398.0, "confidence": 0.97},
}

BANK_JSON = {
    "period_start": "2024-07-01", "period_end": "2024-07-31",
    "opening_balance": {"value": 41124.18, "confidence": 0.99},
    "closing_balance": {"value": 60269.09, "confidence": 0.99},
    "transactions": [
        {"date": "2024-07-01", "description": "SUMUP PAYOUTS",
         "paid_in": 3800.72, "paid_out": None, "balance": 44924.90,
         "page": 1, "confidence": 0.98},
        {"date": "2024-07-01", "description": "RENT BRIDGNORTH ESTATES LLP",
         "paid_in": None, "paid_out": 2166.67, "balance": 42758.23,
         "page": 1, "confidence": 0.65},  # low confidence -> review
    ],
}

LEASE_JSON = {
    "landlord": "Bridgnorth Estates LLP",
    "tenant": "The Copper Kettle Café Ltd",
    "premises": "14 Wharf Street, Shrewsbury SY1 1LN",
    "start_date": "2021-09-29", "term_years": 10,
    "annual_rent": {"value": 26000.0, "confidence": 0.99},
    "rent_page": 2,
    "break_clause": {"exists": True, "break_date": "2026-09-29",
                     "notice_months": 6, "page": 3, "confidence": 0.95},
    "rent_review_date": "2026-09-29",
    "inside_lta_1954": {"value": True, "page": 3, "confidence": 0.9},
}


def test_doc_type_mapping():
    assert doc_type_for("statutory_accounts_fye2025.pdf") == "statutory_accounts"
    assert doc_type_for("bank_statement_2024-07.pdf") == "bank_statement"
    assert doc_type_for("vat_return_2024-06.pdf") == "vat_return"
    assert doc_type_for("management_pnl.pdf") == "management_pnl"
    assert doc_type_for("lease.pdf") == "lease"
    assert doc_type_for("random.pdf") is None


def test_vat_facts_carry_pence_and_provenance():
    facts = build_facts("vat_return", VAT_JSON, dataroom="r", tier="clean",
                        source_doc="vat_return_2024-06.pdf", extractor="fake")
    by_type = {f.fact_type: f for f in facts}
    box6 = by_type[FactType.VAT_BOX6]
    assert box6.value_pence == 98_915_00
    assert box6.period_end == dt.date(2024, 6, 30)
    assert box6.source_doc == "vat_return_2024-06.pdf"
    assert box6.page == 1
    box1 = by_type[FactType.VAT_BOX1]
    assert box1.value_pence == 16_325_78


def test_bank_facts_direction_and_review_flag():
    facts = build_facts("bank_statement", BANK_JSON, dataroom="r",
                        tier="clean", source_doc="bank_statement_2024-07.pdf",
                        extractor="fake")
    txns = [f for f in facts if f.fact_type == FactType.BANK_TXN]
    assert len(txns) == 2
    sumup, rent = txns
    assert sumup.attrs["direction"] == "in"
    assert sumup.value_pence == 3_800_72
    assert rent.attrs["direction"] == "out"
    assert rent.needs_review  # 0.65 < threshold
    assert not sumup.needs_review


def test_lease_facts_break_clause():
    facts = build_facts("lease", LEASE_JSON, dataroom="r", tier="clean",
                        source_doc="lease.pdf", extractor="fake")
    by_type = {f.fact_type: f for f in facts}
    brk = by_type[FactType.LEASE_BREAK_DATE]
    assert brk.value_date == dt.date(2026, 9, 29)
    assert brk.attrs["notice_months"] == 6
    assert brk.page == 3
    assert by_type[FactType.LEASE_INSIDE_LTA_1954].value_text == "inside"
    assert by_type[FactType.LEASE_ANNUAL_RENT].value_pence == 26_000_00


# --- Pipeline against Postgres ------------------------------------------


@pytest.fixture()
def conn():
    psycopg = pytest.importorskip("psycopg")
    from diligence.facts import connect, init_db

    try:
        c = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (docker compose up -d)")
    init_db(c)
    yield c
    c.execute("DELETE FROM fact WHERE dataroom = 'pipe_test'")
    c.commit()
    c.close()


@pytest.fixture()
def room(tmp_path):
    tier = tmp_path / "clean"
    tier.mkdir()
    for name in ("vat_return_2024-06.pdf", "bank_statement_2024-07.pdf",
                 "lease.pdf", "broken_statutory_accounts.pdf"):
        (tier / name).write_bytes(b"%PDF-fake")
    # rename so the broken doc maps to a real doc type but has no response
    (tier / "broken_statutory_accounts.pdf").rename(
        tier / "statutory_accounts_fye2025.pdf")
    return tmp_path


def test_pipeline_loads_facts_and_isolates_failures(conn, room):
    from diligence.facts.db import fetch_facts

    extractor = FakeExtractor(responses={
        "vat_return_2024-06.pdf": VAT_JSON,
        "bank_statement_2024-07.pdf": BANK_JSON,
        "lease.pdf": LEASE_JSON,
        # statutory_accounts_fye2025.pdf missing -> KeyError -> failure
    })
    result = extract_dataroom(conn, extractor, room, "clean",
                              dataroom="pipe_test")
    assert result.documents == 3
    assert len(result.failures) == 1
    assert "statutory_accounts_fye2025.pdf" in result.failures[0]
    assert result.needs_review == 1

    rows = fetch_facts(conn, "pipe_test", "clean")
    assert len(rows) == result.facts
    assert {r["doc_type"] for r in rows} == {"vat_return", "bank_statement",
                                             "lease"}

    # Re-running clears and reloads (idempotent)
    result2 = extract_dataroom(conn, extractor, room, "clean",
                               dataroom="pipe_test")
    assert len(fetch_facts(conn, "pipe_test", "clean")) == result2.facts
