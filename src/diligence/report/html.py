"""Red Flag Report — self-contained HTML (inline CSS, print-friendly)."""

from __future__ import annotations

import datetime as dt
from html import escape

from diligence.checks.base import Finding
from diligence.report.sufficiency import SufficiencyReport

_SEVERITY_META = {
    "red": ("Red flag", "#b3261e", "#fdeceb"),
    "amber": ("Amber", "#9a6a00", "#fdf4e0"),
    "info": ("Noted", "#1f5f3f", "#eaf4ee"),
}

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: #1c1b1a; background: #f6f5f2; line-height: 1.55; font-size: 15px;
}
.page { max-width: 880px; margin: 0 auto; padding: 48px 40px 80px; }
header.masthead { border-bottom: 3px solid #1c1b1a; padding-bottom: 20px; margin-bottom: 32px; }
.masthead .kicker { text-transform: uppercase; letter-spacing: .14em; font-size: 12px; color: #6b6660; font-weight: 600; }
.masthead h1 { font-size: 30px; letter-spacing: -.01em; margin: 6px 0 2px; }
.masthead .meta { color: #6b6660; font-size: 13.5px; margin-top: 6px; }
.summary { display: flex; gap: 14px; margin: 28px 0 8px; }
.tile { flex: 1; background: #fff; border: 1px solid #e4e1db; border-radius: 10px; padding: 14px 16px; }
.tile .n { font-size: 30px; font-weight: 700; letter-spacing: -.02em; }
.tile .l { font-size: 12px; text-transform: uppercase; letter-spacing: .1em; color: #6b6660; font-weight: 600; }
.tile.red .n { color: #b3261e; } .tile.amber .n { color: #9a6a00; } .tile.info .n { color: #1f5f3f; }
section { margin-top: 40px; }
section > h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .14em; color: #6b6660; border-bottom: 1px solid #e4e1db; padding-bottom: 8px; margin-bottom: 18px; }
.suff { background: #fff; border: 1px solid #e4e1db; border-radius: 10px; padding: 20px 22px; }
.suff .score-row { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
.suff .score { font-size: 40px; font-weight: 700; letter-spacing: -.02em; }
.suff .score small { font-size: 16px; color: #6b6660; font-weight: 500; }
.bar { height: 8px; background: #edeae4; border-radius: 4px; overflow: hidden; flex: 1; align-self: center; }
.bar i { display: block; height: 100%; background: #1c1b1a; }
.suff table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.suff td { padding: 5px 0; border-top: 1px solid #f0ede8; }
.suff td.num { text-align: right; font-variant-numeric: tabular-nums; color: #6b6660; }
.ok { color: #1f5f3f; font-weight: 600; } .gap { color: #b3261e; font-weight: 600; }
.finding { background: #fff; border: 1px solid #e4e1db; border-left-width: 5px; border-radius: 10px; padding: 20px 22px; margin-bottom: 16px; page-break-inside: avoid; }
.finding .head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.chip { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; padding: 3px 9px; border-radius: 99px; }
.checkid { font-size: 12px; color: #6b6660; font-family: ui-monospace, Menlo, monospace; }
.period { font-size: 12px; color: #6b6660; margin-left: auto; }
.finding p.body { font-size: 15px; margin-bottom: 12px; }
.evidence { margin: 0 0 12px; padding: 10px 14px; background: #faf9f6; border: 1px dashed #ddd9d1; border-radius: 8px; }
.evidence .etitle { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #6b6660; margin-bottom: 6px; }
.evidence ul { list-style: none; padding: 0; font-size: 13px; }
.evidence li { padding: 2px 0; font-family: ui-monospace, Menlo, monospace; font-size: 12.5px; color: #3d3a36; }
.evidence li b { color: #1c1b1a; font-weight: 600; }
.actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.action { border-radius: 8px; padding: 10px 14px; font-size: 13.5px; }
.action .atitle { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px; }
.action.ask { background: #f0f3f7; } .action.ask .atitle { color: #274a76; }
.action.warranty { background: #f4f0f7; } .action.warranty .atitle { color: #5b3a80; }
.clear { background: #fff; border: 1px solid #e4e1db; border-radius: 10px; padding: 22px; color: #1f5f3f; font-weight: 600; }
footer { margin-top: 56px; padding-top: 16px; border-top: 1px solid #e4e1db; color: #8a857d; font-size: 12px; }
@media print {
  body { background: #fff; font-size: 12.5px; }
  .page { padding: 0; max-width: none; }
  .finding { border-color: #ccc; }
}
"""


def _finding_html(f: Finding) -> str:
    label, color, bg = _SEVERITY_META[f.severity]
    period = ""
    if f.period_start and f.period_end:
        period = f"<span class='period'>{f.period_start:%b %Y} – {f.period_end:%b %Y}</span>"
    evidence_items = "".join(
        f"<li><b>{escape(e.doc_id)}</b> · p.{e.page} · {escape(e.value)}</li>"
        for e in f.evidence)
    return f"""
<article class="finding" style="border-left-color:{color}">
  <div class="head">
    <span class="chip" style="color:{color};background:{bg}">{label}</span>
    <span class="checkid">{escape(f.check_id)}</span>
    {period}
  </div>
  <p class="body">{escape(f.finding)}</p>
  <div class="evidence">
    <div class="etitle">Evidence</div>
    <ul>{evidence_items}</ul>
  </div>
  <div class="actions">
    <div class="action ask"><div class="atitle">Ask the seller</div>{escape(f.ask_the_seller)}</div>
    <div class="action warranty"><div class="atitle">Protect yourself in the SPA</div>{escape(f.warranty_suggestion)}</div>
  </div>
</article>"""


def render_report(company_name: str, company_number: str,
                  findings: list[Finding], sufficiency: SufficiencyReport,
                  dataroom: str, tier: str,
                  generated: dt.date | None = None) -> str:
    generated = generated or dt.date.today()
    reds = [f for f in findings if f.severity == "red"]
    ambers = [f for f in findings if f.severity == "amber"]
    infos = [f for f in findings if f.severity == "info"]

    suff_rows = "".join(
        f"<tr><td>{escape(i.label)}</td>"
        f"<td class='num'>{i.have} / {i.want}</td>"
        f"<td class='num'>{'<span class=ok>✓</span>' if i.complete else '<span class=gap>gap</span>'}</td></tr>"
        for i in sufficiency.items)
    gaps_html = ""
    if sufficiency.gaps:
        gap_list = "".join(f"<li>{escape(g)}</li>" for g in sufficiency.gaps)
        gaps_html = (f"<p style='margin-top:12px;font-size:13.5px'>"
                     f"<b>Gaps to close before relying on this report:</b></p>"
                     f"<ul style='font-size:13.5px;padding-left:18px'>{gap_list}</ul>")

    def section(title: str, items: list[Finding]) -> str:
        if not items:
            return ""
        body = "".join(_finding_html(f) for f in items)
        return f"<section><h2>{escape(title)}</h2>{body}</section>"

    all_clear = ""
    if not reds and not ambers:
        if sufficiency.score >= 50:
            all_clear = ("<section><h2>Findings</h2><div class='clear'>No "
                         "reconciliation discrepancies found across the "
                         "checks run. The documents agree with each other "
                         "and with the external registers checked."
                         "</div></section>")
        else:
            all_clear = ("<section><h2>Findings</h2><div class='clear' "
                         "style='color:#9a6a00'>No discrepancies were found, "
                         "but with a document sufficiency score of "
                         f"{sufficiency.score}/100 there was too little "
                         "evidence to reconcile. This is NOT a clean bill of "
                         "health — close the gaps above before drawing any "
                         "comfort from this report.</div></section>")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Red Flag Report — {escape(company_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <div class="kicker">Diligence OS · Red Flag Report</div>
    <h1>{escape(company_name)}</h1>
    <div class="meta">Company No. {escape(company_number)} · Data room:
    {escape(dataroom)} ({escape(tier)} documents) · Generated {generated:%-d %B %Y}</div>
  </header>

  <div class="summary">
    <div class="tile red"><div class="n">{len(reds)}</div><div class="l">Red flags</div></div>
    <div class="tile amber"><div class="n">{len(ambers)}</div><div class="l">Amber</div></div>
    <div class="tile info"><div class="n">{len(infos)}</div><div class="l">Confirmations</div></div>
    <div class="tile"><div class="n">{sufficiency.score}<small>/100</small></div><div class="l">Document sufficiency</div></div>
  </div>

  <section>
    <h2>1 · Can these documents be relied on?</h2>
    <div class="suff">
      <div class="score-row">
        <div class="score">{sufficiency.score}<small> / 100</small></div>
        <div class="bar"><i style="width:{sufficiency.score}%"></i></div>
      </div>
      <table>{suff_rows}</table>
      {gaps_html}
    </div>
  </section>

  {section("2 · Red flags — resolve before going further", reds)}
  {section("3 · Amber — needs an answer", ambers)}
  {all_clear}
  {section("Confirmations", infos)}

  <footer>
    Every finding above cites its source document and page; findings without
    documentary evidence are structurally impossible in this pipeline.
    This report is a document-reconciliation analysis, not accounting,
    legal or tax advice. Figures extracted below the confidence threshold
    are excluded from checks and listed as verification gaps.
  </footer>
</div>
</body>
</html>"""
