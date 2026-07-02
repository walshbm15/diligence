"""Shared helpers for document renderers (reportlab)."""

from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

PAGE = A4
MARGIN = 18 * mm

INK = colors.HexColor("#1a1a1a")
GREY = colors.HexColor("#555555")
RULE = colors.HexColor("#999999")

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13,
                      textColor=INK)
TITLE = ParagraphStyle("title", parent=BASE, fontName="Helvetica-Bold",
                       fontSize=15, leading=19, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=11,
                    leading=15, spaceBefore=10, spaceAfter=4)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=8, leading=11,
                       textColor=GREY)
CLAUSE = ParagraphStyle("clause", parent=BASE, fontSize=9.5, leading=14,
                        spaceAfter=6)


def money(pence: int, *, pounds_only: bool = False, brackets_negative: bool = True) -> str:
    """Format pence as a UK accounts figure. Negatives in brackets."""
    negative = pence < 0
    p = abs(pence)
    s = f"{round(p / 100):,}" if pounds_only else f"{p / 100:,.2f}"
    if negative and brackets_negative:
        return f"({s})"
    return f"-{s}" if negative else s


def ukdate(d: dt.date) -> str:
    return d.strftime("%-d %B %Y")


def short_date(d: dt.date) -> str:
    return d.strftime("%d %b %y")


def doc_template(path: str, *, landscape_mode: bool = False) -> SimpleDocTemplate:
    from reportlab.lib.pagesizes import landscape

    size = landscape(PAGE) if landscape_mode else PAGE
    return SimpleDocTemplate(
        path, pagesize=size, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=path.rsplit("/", 1)[-1],
    )
