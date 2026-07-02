"""HMRC VAT return — one page per quarter, MTD submission-receipt style."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from diligence.dataroom.spec import CompanyInfo, VatReturnData
from diligence.render.common import BASE, H2, INK, SMALL, TITLE, doc_template

VRN = "384 2917 56"

BOX_LABELS = [
    ("1", "VAT due in the period on sales and other outputs"),
    ("2", "VAT due in the period on acquisitions of goods made in Northern "
          "Ireland from EU member states"),
    ("3", "Total VAT due (the sum of boxes 1 and 2)"),
    ("4", "VAT reclaimed in the period on purchases and other inputs"),
    ("5", "Net VAT to pay to HMRC or reclaim"),
    ("6", "Total value of sales and all other outputs excluding any VAT"),
    ("7", "Total value of purchases and all other inputs excluding any VAT"),
    ("8", "Total value of dispatches of goods and related costs (excluding "
          "VAT) from Northern Ireland to EU member states"),
    ("9", "Total value of acquisitions of goods and related costs (excluding "
          "VAT) made in Northern Ireland from EU member states"),
]


def _fmt(pence: int, whole_pounds: bool) -> str:
    return f"{pence // 100:,}.00" if whole_pounds else f"{pence / 100:,.2f}"


def render_vat_return(company: CompanyInfo, data: VatReturnData, path: str) -> None:
    doc = doc_template(path)
    values = {
        "1": _fmt(data.box1, False), "2": _fmt(data.box2, False),
        "3": _fmt(data.box3, False), "4": _fmt(data.box4, False),
        "5": _fmt(data.box5, False), "6": _fmt(data.box6, True),
        "7": _fmt(data.box7, True), "8": "0.00", "9": "0.00",
    }

    period = (f"{data.period_start.strftime('%d %B %Y')} to "
              f"{data.period_end.strftime('%d %B %Y')}")
    rows = [[b, Paragraph(label, BASE), values[b]] for b, label in BOX_LABELS]
    t = Table(rows, colWidths=[10 * mm, 120 * mm, 34 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b8bc")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef3f5")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    doc.build([
        Paragraph("HM Revenue &amp; Customs", TITLE),
        Paragraph("Submitted VAT Return — Making Tax Digital", H2),
        Spacer(0, 2 * mm),
        Paragraph(f"Business name: <b>{company.name}</b>", BASE),
        Paragraph(f"VAT registration number: <b>{VRN}</b>", BASE),
        Paragraph(f"Period: <b>{period}</b>", BASE),
        Spacer(0, 5 * mm),
        t,
        Spacer(0, 5 * mm),
        Paragraph(
            "This return was submitted through Making Tax Digital compatible "
            "software. Figures in boxes 6 to 9 are shown in whole pounds.",
            SMALL),
    ])
