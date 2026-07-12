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


# --- Real-folder ingestion ----------------------------------------------


def test_scan_folder_accounts_for_every_file(tmp_path):
    from diligence.ingest import scan_folder

    (tmp_path / "financials").mkdir()
    (tmp_path / "financials" / "Q2 24 return HMRC.pdf").write_bytes(b"%PDF")
    (tmp_path / "lease scan.pdf").write_bytes(b"%PDF")
    (tmp_path / "suppliers.xlsx").write_bytes(b"xx")
    (tmp_path / "notes.docx").write_bytes(b"xx")
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / "__MACOSX").mkdir()
    (tmp_path / "__MACOSX" / "._lease scan.pdf").write_bytes(b"junk")

    inv = scan_folder(tmp_path)
    assert [p.as_posix() for p in inv.pdfs] == [
        "financials/Q2 24 return HMRC.pdf", "lease scan.pdf"]
    assert [p.as_posix() for p in inv.unsupported] == [
        "notes.docx", "suppliers.xlsx"]
    assert inv.ignored == 2  # .DS_Store + __MACOSX resource fork


def test_unpack_zip(tmp_path):
    import zipfile

    from diligence.ingest import unpack_zip

    zip_path = tmp_path / "dataroom.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("accounts/fy25.pdf", "%PDF")
    root = unpack_zip(zip_path)
    assert root == tmp_path / "dataroom"
    assert (root / "accounts" / "fy25.pdf").exists()
    # Second call is a no-op, not a re-extract
    assert unpack_zip(zip_path) == root


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


def test_ingest_folder_end_to_end(tmp_path, messy_room):
    import psycopg

    from diligence.extraction.extractor import FakeExtractor
    from diligence.facts import connect, init_db
    from diligence.facts.db import fetch_facts, row_to_fact
    from diligence.ingest import REAL_TIER, Classifier, ingest_folder
    from diligence.report.generate import build_report

    try:
        conn = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    init_db(conn)

    # A believable real folder: nested dirs, a spreadsheet, OS junk, and a
    # PDF the classifier can't place.
    (tmp_path / "financials").mkdir()
    vat_src = next(p for p in messy_room.glob("*.pdf") if "return" in p.name)
    shutil.copy(vat_src, tmp_path / "financials" / "Q2 24 return HMRC.pdf")
    (tmp_path / "suppliers.xlsx").write_bytes(b"xx")
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(tmp_path / "holiday rota.pdf"))
    c.drawString(100, 700, "Staff holiday rota")
    c.save()

    extractor = FakeExtractor(responses={"Q2 24 return HMRC.pdf": VAT_JSON})
    try:
        result = ingest_folder(conn, extractor, tmp_path,
                               dataroom="ingest_folder_test",
                               classifier=Classifier(use_llm=False))
        assert result.documents == 1
        assert result.by_type == {"vat_return": 1}
        assert result.unclassified == ["holiday rota.pdf"]
        assert result.unsupported == ["suppliers.xlsx"]
        assert result.ignored == 1

        # source_doc is the RELATIVE PATH, so nested duplicates can't collide
        rows = fetch_facts(conn, "ingest_folder_test", REAL_TIER)
        assert rows and all(
            r["source_doc"] == "financials/Q2 24 return HMRC.pdf"
            for r in rows)

        # resume skips paid work
        again = ingest_folder(conn, extractor, tmp_path,
                              dataroom="ingest_folder_test", resume=True,
                              classifier=Classifier(use_llm=False))
        assert again.skipped == 1 and again.documents == 0

        # The report path needs no manifest/claims/fixture for a real room
        facts = [row_to_fact(r) for r in rows]
        path = build_report(
            facts, claims=[], companies_house=None,
            company_name="Test Café Ltd", company_number="",
            dataroom="ingest_folder_test", tier=REAL_TIER,
            out_dir=tmp_path / "out")
        assert path.exists()
        assert path.suffix in (".pdf", ".html")
    finally:
        conn.execute("DELETE FROM fact WHERE dataroom='ingest_folder_test'")
        conn.commit()
        conn.close()


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
