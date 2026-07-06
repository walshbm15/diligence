"""Sweep real Companies House café accounts through extraction (issue #21).

Downloads the latest filed accounts for active SIC-56102 companies from the
public CH website, extracts each, and reports: confident vs quarantined
facts, whether the balance-sheet equation ties from the extracted figures,
and any pipeline failures. Facts land under dataroom='ch_sweep'.
"""

import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://find-and-update.company-information.service.gov.uk"
OUT = Path("data_rooms/ch_sweep/clean")
TARGET = 12


def log(msg):
    print(msg, flush=True)


def find_companies(pages: int = 3) -> list[str]:
    numbers: list[str] = []
    with httpx.Client(timeout=30) as web:
        for page in range(1, pages + 1):
            r = web.get(f"{BASE}/advanced-search/get-results",
                        params={"sicCodes": "56102", "status": "active",
                                "page": page})
            found = re.findall(r"/company/([0-9A-Z]{8})", r.text)
            for n in found:
                if n not in numbers:
                    numbers.append(n)
            time.sleep(1)
    return numbers


def latest_accounts_link(web: httpx.Client, number: str) -> tuple[str, str] | None:
    r = web.get(f"{BASE}/company/{number}/filing-history")
    rows = re.split(r"<tr", r.text)
    for row in rows:
        if re.search(r"accounts", row, re.I) and "document?format=pdf" in row:
            if re.search(r"dormant", row, re.I):
                return None  # latest accounts are dormant — skip company
            desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row))
            m = re.search(r"(accounts made up to [0-9]+ \w+ [0-9]{4})", desc, re.I)
            link = re.search(
                rf'/company/{number}/filing-history/[A-Za-z0-9_=-]+'
                r'/document\?format=pdf[^"]*', row)
            if link:
                url = link.group(0).replace("&amp;", "&")
                return url, (m.group(1) if m else "accounts")
    return None


def download_accounts() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    got = sorted(OUT.glob("*.pdf"))
    if len(got) >= TARGET:
        log(f"already have {len(got)} PDFs")
        return got
    numbers = find_companies()
    log(f"candidates: {len(numbers)}")
    with httpx.Client(timeout=60, follow_redirects=True) as web:
        for number in numbers:
            if len(list(OUT.glob("*.pdf"))) >= TARGET:
                break
            try:
                hit = latest_accounts_link(web, number)
                if hit is None:
                    continue
                url, desc = hit
                dest = OUT / f"real_{number}.pdf"
                if dest.exists():
                    continue
                r = web.get(BASE + url)
                if r.status_code == 200 and r.content[:4] == b"%PDF":
                    dest.write_bytes(r.content)
                    log(f"  {number}: {desc} ({len(r.content) // 1024}KB)")
            except httpx.HTTPError as exc:
                log(f"  {number}: fetch failed ({exc})")
            time.sleep(1.2)
    return sorted(OUT.glob("*.pdf"))


def sweep(pdfs: list[Path]) -> int:
    from diligence.extraction.extractor import ClaudeExtractor
    from diligence.extraction.facts_builder import build_facts
    from diligence.facts import connect, init_db, insert_facts
    from diligence.facts.db import clear_dataroom

    conn = connect()
    init_db(conn)
    clear_dataroom(conn, "ch_sweep")
    extractor = ClaudeExtractor()
    failures, rows = [], []
    for pdf in pdfs:
        try:
            data = extractor.extract(pdf, "statutory_accounts")
            facts = build_facts("statutory_accounts", data,
                                dataroom="ch_sweep", tier="clean",
                                source_doc=pdf.name, extractor=extractor.name)
            insert_facts(conn, facts)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{pdf.name}: {exc}")
            log(f"FAIL {pdf.name}: {str(exc)[:120]}")
            continue

        confident = [f for f in facts if f.confidence >= 0.8]
        quarantined = [f for f in facts if f.confidence < 0.8]
        by = {f.fact_type: f.value_pence for f in confident
              if f.value_pence is not None}
        # Balance-sheet equation from extracted figures only
        tie = "n/a"
        # Fixed assets / long creditors / accruals are legitimately absent
        # lines on many filings — treat absent as zero.
        needed = ("stat_current_assets", "stat_creditors_within_year",
                  "stat_net_assets")
        if all(k in by for k in needed):
            lhs = (by.get("stat_fixed_assets", 0) + by["stat_current_assets"]
                   - by["stat_creditors_within_year"]
                   - by.get("stat_creditors_after_year", 0)
                   - by.get("stat_accruals_deferred", 0))
            tie = "TIES" if abs(lhs - by["stat_net_assets"]) <= 200 else (
                f"OFF by £{abs(lhs - by['stat_net_assets']) / 100:,.0f}")
        rows.append((pdf.name, len(confident), len(quarantined), tie))
        log(f"  {pdf.name}: {len(confident)} confident, "
            f"{len(quarantined)} quarantined, balance sheet {tie}")

    log("\nSWEEP SUMMARY")
    log(f"{'file':26} {'conf':>4} {'quar':>4}  balance-sheet")
    for name, c, q, tie in rows:
        log(f"{name:26} {c:>4} {q:>4}  {tie}")
    ties = sum(1 for r in rows if r[3] == "TIES")
    log(f"\n{len(rows)} extracted, {len(failures)} failures, "
        f"{ties}/{len(rows)} balance sheets tie from extracted figures")
    u = extractor.usage
    log(f"API: {u.calls} calls, ~${u.cost_usd:.2f}")
    conn.close()
    return 0 if not failures else 1


if __name__ == "__main__":
    pdfs = download_accounts()
    log(f"{len(pdfs)} PDFs ready")
    sys.exit(sweep(pdfs))
