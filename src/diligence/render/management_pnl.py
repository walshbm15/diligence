"""Management P&L — landscape monthly table, one financial year per page."""

from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from diligence.dataroom.spec import CompanyInfo, ManagementPnlData, PnlRow
from diligence.render.common import BASE, H2, INK, RULE, SMALL, doc_template, money


def _year_table(months: list[PnlRow]) -> Table:
    def row(label, values, *, negate=False, bold=False):
        out = [label]
        total = 0
        for v in values:
            total += v
            out.append(money(-v if negate else v, pounds_only=True))
        out.append(money(-total if negate else total, pounds_only=True))
        return out, bold

    headers = ["", *[m.period_start.strftime("%b %y") for m in months], "Total"]
    spec = [
        row("Revenue", [m.revenue for m in months], bold=True),
        row("Cost of sales", [m.cogs for m in months], negate=True),
        row("Gross profit", [m.gross_profit for m in months], bold=True),
        row("Staff costs", [m.staff_costs for m in months], negate=True),
        row("Rent", [m.rent for m in months], negate=True),
        row("Overheads", [m.overheads for m in months], negate=True),
        row("Card fees", [m.card_fees for m in months], negate=True),
        row("Depreciation", [m.depreciation for m in months], negate=True),
        row("Loan interest", [m.loan_interest for m in months], negate=True),
        row("Net profit", [m.profit_before_tax for m in months], bold=True),
    ]
    data = [headers] + [r for r, _b in spec]
    widths = [26 * mm] + [17.4 * mm] * len(months) + [19 * mm]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (-1, 0), (-1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK),
        ("LINEABOVE", (0, 3), (-1, 3), 0.4, RULE),
        ("LINEABOVE", (0, 10), (-1, 10), 0.7, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i, (_r, bold) in enumerate(spec, start=1):
        if bold:
            style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


def render_management_pnl(company: CompanyInfo, data: ManagementPnlData,
                          path: str) -> None:
    doc = doc_template(path, landscape_mode=True)
    story = []
    months = data.months
    for start in range(0, len(months), 12):
        chunk = months[start:start + 12]
        fy_end = chunk[-1].period_end
        if start:
            story.append(PageBreak())
        story += [
            Paragraph(company.name, H2),
            Paragraph(
                f"Management Profit && Loss — 12 months to {fy_end.strftime('%d %B %Y')}"
                .replace("&&", "&amp;"), BASE),
            Paragraph("All figures £, unaudited, prepared internally", SMALL),
            Spacer(0, 4 * mm),
            _year_table(chunk),
        ]
    doc.build(story)
