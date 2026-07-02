"""Renderer tests: every doc type renders, and degradation is deterministic."""

import pypdfium2 as pdfium
import pytest

from diligence.dataroom.build import render_spec
from diligence.dataroom.spec import build_spec
from diligence.ledger import generate_ledger
from diligence.render.quality import degrade


@pytest.fixture(scope="module")
def spec():
    return build_spec(generate_ledger())


@pytest.fixture(scope="module")
def rendered(spec, tmp_path_factory):
    out = tmp_path_factory.mktemp("clean")
    paths = render_spec(spec, out)
    return out, paths


def test_renders_all_documents(rendered):
    _out, paths = rendered
    names = {p.name for p in paths}
    assert "statutory_accounts_fye2025.pdf" in names
    assert "statutory_accounts_fye2026.pdf" in names
    assert "management_pnl.pdf" in names
    assert "lease.pdf" in names
    assert sum(1 for n in names if n.startswith("bank_statement_")) == 24
    assert sum(1 for n in names if n.startswith("vat_return_")) == 8
    assert len(paths) == 36
    for p in paths:
        assert p.stat().st_size > 1000


def test_statutory_accounts_have_expected_pages(rendered):
    out, _paths = rendered
    doc = pdfium.PdfDocument(str(out / "statutory_accounts_fye2025.pdf"))
    assert len(doc) == 4  # cover, income statement, balance sheet, notes
    doc.close()


def test_second_year_accounts_show_prior_comparatives(spec):
    fy2 = spec.statutory_accounts[1]
    assert fy2.prior_income is spec.statutory_accounts[0]
    assert fy2.prior is spec.statutory_accounts[0].balance


def test_statutory_accounts_tie_in_whole_pounds(spec):
    for acc in spec.statutory_accounts:
        assert acc.turnover % 100 == 0
        computed = (acc.turnover - acc.raw_materials - acc.staff_costs
                    - acc.depreciation - acc.other_charges)
        assert acc.profit_before_tax == computed
        b = acc.balance
        net = (b.fixed_assets + b.stock + b.debtors + b.cash
               - b.creditors_within_year - b.creditors_after_year)
        assert net == b.share_capital + b.retained_earnings
        assert (b.note_vat + b.note_paye + b.note_ct + b.note_loan_within_year
                == b.creditors_within_year)


def test_degrade_is_deterministic(rendered, tmp_path):
    out, _paths = rendered
    src = out / "vat_return_2024-06.pdf"
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    degrade(src, a, "scanned")
    degrade(src, b, "scanned")
    assert a.read_bytes() == b.read_bytes()


def test_degraded_pdf_has_no_text_layer(rendered, tmp_path):
    out, _paths = rendered
    src = out / "vat_return_2024-06.pdf"
    dst = tmp_path / "scan.pdf"
    degrade(src, dst, "scanned")
    doc = pdfium.PdfDocument(str(dst))
    text = doc[0].get_textpage().get_text_range()
    doc.close()
    assert text.strip() == ""  # image-only: extraction must OCR
