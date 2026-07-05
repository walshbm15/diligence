"""Classifier tests: real-world messy filenames must not defeat ingestion."""

import shutil

import pytest

from diligence.dataroom.build import render_spec
from diligence.dataroom.spec import build_spec
from diligence.ingest import Classifier, classify_by_text
from diligence.ledger import generate_ledger

MESSY_NAMES = {
    "statutory_accounts_fye2025.pdf": "Copper Kettle FY25 accounts FINAL(2).pdf",
    "management_pnl.pdf": "P&L monthly mgmt 24m v3.pdf",
    "bank_statement_2024-07.pdf": "July 24 statement - business acct.pdf",
    "vat_return_2024-06.pdf": "Q2 24 return HMRC.pdf",
    "lease.pdf": "14 Wharf St signed agreement.pdf",
}

EXPECTED = {
    "Copper Kettle FY25 accounts FINAL(2).pdf": "statutory_accounts",
    "P&L monthly mgmt 24m v3.pdf": "management_pnl",
    "July 24 statement - business acct.pdf": "bank_statement",
    "Q2 24 return HMRC.pdf": "vat_return",
    "14 Wharf St signed agreement.pdf": "lease",
}


@pytest.fixture(scope="module")
def messy_room(tmp_path_factory):
    out = tmp_path_factory.mktemp("messy")
    spec = build_spec(generate_ledger())
    rendered = tmp_path_factory.mktemp("rendered")
    paths = {p.name: p for p in render_spec(spec, rendered)}
    for orig, messy in MESSY_NAMES.items():
        shutil.copy(paths[orig], out / messy)
    return out


def test_text_rules_classify_all_five_types(messy_room):
    classifier = Classifier(use_llm=False)  # text layer only, no API
    for pdf in messy_room.glob("*.pdf"):
        assert classifier.classify(pdf) == EXPECTED[pdf.name], pdf.name
    assert classifier.llm_calls == 0


def test_filename_convention_still_wins(messy_room, tmp_path):
    # A conventionally-named file skips content inspection entirely
    src = next(messy_room.glob("*statement*"))
    conventional = tmp_path / "bank_statement_2024-07.pdf"
    shutil.copy(src, conventional)
    assert Classifier(use_llm=False).classify(conventional) == "bank_statement"


def test_unknown_document_returns_none(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    p = tmp_path / "holiday rota 2025.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    c.drawString(100, 700, "Staff holiday rota for summer 2025")
    c.save()
    assert Classifier(use_llm=False).classify(p) is None


def test_scanned_pdf_has_no_text_and_needs_llm(tmp_path, messy_room):
    from diligence.render.quality import degrade

    src = next(p for p in messy_room.glob("*.pdf") if "return" in p.name)
    scan = tmp_path / "old scan.pdf"
    degrade(src, scan, "scanned")
    # Without the LLM fallback an image-only PDF is honestly unclassifiable
    assert Classifier(use_llm=False).classify(scan) is None


def test_text_rule_priorities():
    assert classify_by_text(
        "HM Revenue & Customs Submitted VAT Return Box 1") == "vat_return"
    assert classify_by_text(
        "LEASE between Landlord (1) and Tenant (2) yearly rent") == "lease"
    assert classify_by_text(
        "Statement of account Sort code 40-32-16 Paid out") == "bank_statement"
    # statutory accounts mention 'profit and loss account' — must not
    # misclassify as management P&L
    assert classify_by_text(
        "Registered number 13977581 Unaudited Micro-Entity Accounts "
        "Balance Sheet Profit and loss account") == "statutory_accounts"
    assert classify_by_text("") is None


def test_pipeline_reports_unclassified(tmp_path):
    import psycopg

    from diligence.extraction.extractor import FakeExtractor
    from diligence.extraction.pipeline import extract_dataroom
    from diligence.facts import connect, init_db

    try:
        conn = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    init_db(conn)

    tier = tmp_path / "clean"
    tier.mkdir()
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(tier / "mystery.pdf"))
    c.drawString(100, 700, "nothing recognisable here")
    c.save()

    result = extract_dataroom(conn, FakeExtractor(), tmp_path, "clean",
                              dataroom="ingest_test",
                              classifier=Classifier(use_llm=False))
    assert result.unclassified == ["mystery.pdf"]
    assert result.documents == 0
    conn.execute("DELETE FROM fact WHERE dataroom='ingest_test'")
    conn.commit()
    conn.close()
