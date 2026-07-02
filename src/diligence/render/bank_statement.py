"""Monthly business bank statements (fictional high-street bank layout)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from diligence.dataroom.spec import BankStatementData, CompanyInfo
from diligence.render.common import (
    BASE,
    INK,
    RULE,
    SMALL,
    TITLE,
    doc_template,
    money,
    short_date,
)

BANK_NAME = "MIDLAND & SEVERN BANK plc"


def render_bank_statement(company: CompanyInfo, data: BankStatementData,
                          path: str) -> None:
    doc = doc_template(path)
    period = (f"{data.period_start.strftime('%d %B %Y')} to "
              f"{data.period_end.strftime('%d %B %Y')}")

    head = Table([
        [Paragraph(f"<b>{BANK_NAME}</b>", TITLE),
         Paragraph("Business Current Account<br/>Statement of account", BASE)],
        [Paragraph(f"{data.account_name}<br/>{company.registered_office}", BASE),
         Paragraph(
             f"Sort code: {data.sort_code}<br/>"
             f"Account no: {data.account_number}<br/>"
             f"Period: {period}", BASE)],
    ], colWidths=[100 * mm, 74 * mm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LINEBELOW", (0, 1), (-1, 1), 0.8, INK),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))

    rows = [["Date", "Description", "Paid out (£)", "Paid in (£)", "Balance (£)"]]
    rows.append([short_date(data.period_start), "OPENING BALANCE", "", "",
                 money(data.opening_balance)])
    for line in data.lines:
        rows.append([
            short_date(line.date), line.description[:46],
            money(line.paid_out) if line.paid_out else "",
            money(line.paid_in) if line.paid_in else "",
            money(line.balance),
        ])
    rows.append([short_date(data.period_end), "CLOSING BALANCE", "", "",
                 money(data.closing_balance)])

    t = Table(rows, colWidths=[18 * mm, 76 * mm, 26 * mm, 26 * mm, 28 * mm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f4f2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
    ]))

    doc.build([
        head,
        Spacer(0, 4 * mm),
        t,
        Spacer(0, 3 * mm),
        Paragraph(
            f"{BANK_NAME} is authorised by the Prudential Regulation Authority. "
            f"Statement generated {data.period_end.strftime('%d/%m/%Y')}.",
            SMALL),
    ])
