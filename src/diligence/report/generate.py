"""Report generation: facts -> checks -> HTML (-> PDF via headless Chrome)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from diligence.checks import CheckContext, FactIndex, run_all
from diligence.external import CompaniesHouseFixture
from diligence.report.html import render_report
from diligence.report.sufficiency import assess

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
)


def _find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    return None


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    chrome = _find_chrome()
    if chrome is None:
        return False
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", str(html_path)],
        check=True, capture_output=True, timeout=120)
    return True


def build_context(facts, claims: list[dict], room_dir: Path,
                  company_number: str) -> CheckContext:
    ch = None
    fixture = room_dir / "companies_house.json"
    if fixture.exists():
        ch = CompaniesHouseFixture(fixture)
    return CheckContext(facts=FactIndex(facts), claims=claims,
                        companies_house=ch, company_number=company_number)


def generate_report(facts, room_dir: Path, tier: str, out_dir: Path,
                    needs_review: int = 0) -> Path:
    manifest = json.loads((room_dir / "manifest.json").read_text())
    company = manifest["company"]
    claims_file = room_dir / "claims.json"
    claims = json.loads(claims_file.read_text()) if claims_file.exists() else []

    ctx = build_context(facts, claims, room_dir, company["number"])
    findings = run_all(ctx)
    sufficiency = assess(ctx.facts, needs_review=needs_review)

    html = render_report(
        company_name=company["name"], company_number=company["number"],
        findings=findings, sufficiency=sufficiency,
        dataroom=room_dir.name, tier=tier)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"red_flag_report_{room_dir.name}_{tier}.html"
    html_path.write_text(html)
    pdf_path = html_path.with_suffix(".pdf")
    if html_to_pdf(html_path, pdf_path):
        return pdf_path
    return html_path


def _ground_truth_facts(room_dir: Path):
    """Demo path: perfect-extraction facts reconstructed from the spec.

    The room's mutation log tells us whether the planted mutations were
    applied when it was built.
    """
    import dataclasses

    from diligence.dataroom.spec import build_spec
    from diligence.evals.ground_truth import expected_facts
    from diligence.ledger import generate_ledger
    from diligence.mutations import DEFAULT_MUTATIONS, apply_mutations

    spec = build_spec(generate_ledger())
    log = json.loads((room_dir / "mutation_log.json").read_text())
    if log:
        apply_mutations(spec, DEFAULT_MUTATIONS)
    return [dataclasses.replace(f, tier="ground_truth")
            for f in expected_facts(spec, dataroom=room_dir.name)]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a Red Flag Report for a data room")
    parser.add_argument("room_dir", type=Path)
    parser.add_argument("--tier", default="clean")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--ground-truth", action="store_true",
                        help="use spec-derived facts instead of the DB "
                             "(demo without extraction)")
    args = parser.parse_args()

    if args.ground_truth:
        facts = _ground_truth_facts(args.room_dir)
        needs_review = 0
    else:
        from diligence.facts import connect, init_db
        from diligence.facts.db import fetch_facts, row_to_fact

        conn = connect()
        init_db(conn)
        rows = fetch_facts(conn, args.room_dir.name, args.tier)
        facts = [row_to_fact(r) for r in rows]
        needs_review = sum(1 for f in facts if f.needs_review)
        conn.close()
        if not facts:
            raise SystemExit(
                f"No facts for {args.room_dir.name}/{args.tier} — run "
                f"extraction first, or pass --ground-truth for a demo.")

    path = generate_report(facts, args.room_dir, args.tier, args.out,
                           needs_review=needs_review)
    print(f"Report written: {path}")


if __name__ == "__main__":
    main()
