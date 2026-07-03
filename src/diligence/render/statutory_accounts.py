"""Micro-entity statutory accounts (FRS 105 / Companies House layout)."""

from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from diligence.dataroom.spec import CompanyInfo, StatutoryAccountsData
from diligence.render.common import (
    BASE,
    H2,
    INK,
    RULE,
    SMALL,
    TITLE,
    doc_template,
    money,
    ukdate,
)

_NUM_STYLE = TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("TEXTCOLOR", (0, 0), (-1, -1), INK),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
])


def _rule(table: Table, row: int, cols=(1, 2), above=False, double=False):
    cmds = []
    for c in cols:
        if above:
            cmds.append(("LINEABOVE", (c, row), (c, row), 0.7, RULE))
        else:
            cmds.append(("LINEBELOW", (c, row), (c, row),
                         1.1 if double else 0.7, INK if double else RULE))
        if double:
            cmds.append(("LINEBELOW", (c, row), (c, row), 0.5, INK))
    table.setStyle(TableStyle(cmds))


def render_statutory_accounts(company: CompanyInfo, data: StatutoryAccountsData,
                              path: str) -> None:
    doc = doc_template(path)
    fy_label = ukdate(data.fy_end)
    prior = data.prior
    story = [
        Spacer(0, 40 * mm),
        Paragraph(f"Registered number: {company.number}", SMALL),
        Spacer(0, 6 * mm),
        Paragraph(company.name.upper(), TITLE),
        Paragraph("Unaudited Micro-Entity Accounts", H2),
        Paragraph(f"for the year ended {fy_label}", BASE),
        Spacer(0, 60 * mm),
        Paragraph(f"Registered office: {company.registered_office}", SMALL),
        PageBreak(),
    ]

    # --- Income statement -------------------------------------------------
    story += [
        Paragraph(company.name.upper(), H2),
        Paragraph(f"Income Statement for the year ended {fy_label}", BASE),
        Spacer(0, 5 * mm),
    ]
    def gbp(pence: int) -> str:
        return money(pence, pounds_only=True)

    pi = data.prior_income

    def piv(value_fn) -> str:
        return gbp(value_fn(pi)) if pi else "—"

    rows = [
        ["", f"{data.fy_end.year}\n£", f"{data.fy_end.year - 1}\n£"],
        ["Turnover", gbp(data.turnover), piv(lambda a: a.turnover)],
        ["Cost of raw materials and consumables", gbp(-data.raw_materials),
         piv(lambda a: -a.raw_materials)],
        ["Staff costs", gbp(-data.staff_costs), piv(lambda a: -a.staff_costs)],
        ["Depreciation and other amounts written off assets",
         gbp(-data.depreciation), piv(lambda a: -a.depreciation)],
        ["Other charges", gbp(-data.other_charges),
         piv(lambda a: -a.other_charges)],
        ["Profit before tax", gbp(data.profit_before_tax),
         piv(lambda a: a.profit_before_tax)],
        ["Tax", gbp(-data.tax), piv(lambda a: -a.tax)],
        ["Profit for the financial year",
         gbp(data.profit_before_tax - data.tax),
         piv(lambda a: a.profit_before_tax - a.tax)],
    ]
    t = Table(rows, colWidths=[95 * mm, 35 * mm, 30 * mm])
    t.setStyle(_NUM_STYLE)
    t.setStyle(TableStyle([("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
                           ("FONTNAME", (0, 8), (-1, 8), "Helvetica-Bold")]))
    _rule(t, 5, cols=(1,))
    _rule(t, 8, cols=(1,), double=True)
    story += [t, PageBreak()]

    # --- Balance sheet -----------------------------------------------------
    story += [
        Paragraph(company.name.upper(), H2),
        Paragraph(f"Statement of Financial Position as at {fy_label}", BASE),
        Spacer(0, 5 * mm),
    ]

    def bs_col(b):
        current_assets = b.stock + b.debtors + b.cash
        net_current = current_assets - b.creditors_within_year
        total_less_cl = b.fixed_assets + net_current
        net = total_less_cl - b.creditors_after_year
        return {
            "fixed": b.fixed_assets, "current": current_assets,
            "cred1": b.creditors_within_year, "netcur": net_current,
            "total": total_less_cl, "cred2": b.creditors_after_year,
            "net": net, "cap": b.share_capital, "ret": b.retained_earnings,
        }

    cur = bs_col(data.balance)
    pri = bs_col(prior) if prior else None

    def pv(key):
        return money(pri[key], pounds_only=True) if pri else "—"

    def pneg(key):
        return money(-pri[key], pounds_only=True) if pri else "—"

    label_prior = f"{prior.at.year}" if prior else ""
    rows = [
        ["", f"{data.fy_end.year}\n£", f"{label_prior}\n£"],
        ["Fixed assets", gbp(cur["fixed"]), pv("fixed")],
        ["Current assets", gbp(cur["current"]), pv("current")],
        ["Creditors: amounts falling due within one year",
         gbp(-cur["cred1"]), pneg("cred1")],
        ["Net current assets", gbp(cur["netcur"]), pv("netcur")],
        ["Total assets less current liabilities", gbp(cur["total"]), pv("total")],
        ["Creditors: amounts falling due after more than one year",
         gbp(-cur["cred2"]), pneg("cred2")],
        ["Net assets", gbp(cur["net"]), pv("net")],
        ["", "", ""],
        ["Capital and reserves", "", ""],
        ["Called up share capital", gbp(cur["cap"]), pv("cap")],
        ["Profit and loss account", gbp(cur["ret"]), pv("ret")],
        ["Shareholders' funds", gbp(cur["cap"] + cur["ret"]),
         money(pri["cap"] + pri["ret"], pounds_only=True) if pri else "—"],
    ]
    t = Table(rows, colWidths=[95 * mm, 35 * mm, 30 * mm])
    t.setStyle(_NUM_STYLE)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 7), (-1, 7), "Helvetica-Bold"),
        ("FONTNAME", (0, 9), (0, 9), "Helvetica-Bold"),
        ("FONTNAME", (0, 12), (-1, 12), "Helvetica-Bold"),
    ]))
    _rule(t, 3, cols=(1, 2))
    _rule(t, 7, cols=(1, 2), double=True)
    _rule(t, 12, cols=(1, 2), double=True)
    story += [
        t,
        Spacer(0, 8 * mm),
        Paragraph(
            "These accounts have been prepared in accordance with the "
            "micro-entity provisions of the Companies Act 2006 and FRS 105. "
            "The company has taken advantage of the exemption from audit under "
            "section 477 of the Companies Act 2006.", SMALL),
        Spacer(0, 4 * mm),
        Paragraph(
            f"Approved by the board and signed on its behalf by "
            f"{company.director}, Director, on {ukdate(data.fy_end)}.", SMALL),
        PageBreak(),
    ]

    # --- Notes ---------------------------------------------------------------
    b = data.balance
    notes = [
        Paragraph(company.name.upper(), H2),
        Paragraph(f"Notes to the Accounts for the year ended {fy_label}", BASE),
        Spacer(0, 4 * mm),
        Paragraph("1. Average number of employees", H2),
        Paragraph(
            f"The average number of persons employed by the company during the "
            f"year, including the director, was {data.average_employees}.", BASE),
        Paragraph("2. Creditors", H2),
    ]
    cred_rows = [
        ["Amounts falling due within one year:", "£"],
        ["Taxation and social security (VAT, PAYE/NIC)",
         money(b.note_vat + b.note_paye, pounds_only=True)],
        ["Corporation tax", money(b.note_ct, pounds_only=True)],
    ]
    # A seller hiding debt omits the loan lines rather than printing zeros.
    if b.note_loan_within_year:
        cred_rows.append(["Bank loans (current portion)",
                          money(b.note_loan_within_year, pounds_only=True)])
    cred_rows.append(["", money(b.creditors_within_year, pounds_only=True)])
    total_row = len(cred_rows) - 1
    if b.note_loan_after_year:
        cred_rows += [["Amounts falling due after more than one year:", ""],
                      ["Bank loans", money(b.note_loan_after_year,
                                           pounds_only=True)]]
    t = Table(cred_rows, colWidths=[95 * mm, 35 * mm])
    t.setStyle(_NUM_STYLE)
    _rule(t, total_row, cols=(1,))
    notes.append(t)
    if data.loan_disclosure:
        notes += [Spacer(0, 3 * mm), Paragraph(data.loan_disclosure, BASE)]
    story += notes

    doc.build(story)
