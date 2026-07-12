"""Real-world data-room ingestion: an arbitrary folder (or zip) -> facts -> report.

Synthetic rooms follow the render layout (`room/<tier>/*.pdf` plus manifest,
claims and a Companies House fixture). Real data rooms are whatever the
seller emailed over: nested folders, spreadsheets, photos, junk. This path
walks all of it, classifies PDFs by content, extracts what it can and
accounts for every file it couldn't — an incomplete data room is a finding
(the sufficiency score), not a failure.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from diligence.extraction.facts_builder import build_facts
from diligence.extraction.pipeline import _docs_with_facts, replace_doc_facts
from diligence.ingest.classify import Classifier

REAL_TIER = "real"

_JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}
_JUNK_DIRS = {"__macosx"}


@dataclass
class Inventory:
    """Every file in the folder, bucketed. Nothing is silently dropped."""

    root: Path
    pdfs: list[Path] = field(default_factory=list)        # relative paths
    unsupported: list[Path] = field(default_factory=list)  # non-PDF documents
    ignored: int = 0                                       # OS junk only


def _is_junk(rel: Path) -> bool:
    if rel.name.lower() in _JUNK_NAMES or rel.name.startswith("."):
        return True
    return any(part.startswith(".") or part.lower() in _JUNK_DIRS
               for part in rel.parts[:-1])


def scan_folder(root: Path) -> Inventory:
    inv = Inventory(root=root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_junk(rel):
            inv.ignored += 1
        elif path.suffix.lower() == ".pdf":
            inv.pdfs.append(rel)
        else:
            inv.unsupported.append(rel)
    return inv


def unpack_zip(zip_path: Path) -> Path:
    """Real data rooms usually arrive as a zip. Unpack next to it (once)."""
    dest = zip_path.with_suffix("")
    if not dest.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
    return dest


@dataclass
class IngestResult:
    dataroom: str
    documents: int = 0
    skipped: int = 0
    facts: int = 0
    needs_review: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    unclassified: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    ignored: int = 0


def ingest_folder(conn, extractor, root: Path,
                  dataroom: str | None = None,
                  resume: bool = False,
                  classifier: Classifier | None = None) -> IngestResult:
    """Extract every classifiable PDF under `root` into the fact table.

    Unlike `extract_dataroom`, there is no tier subdirectory: the whole tree
    is walked and facts land under tier "real". `source_doc` is the path
    relative to `root` (posix), so identically-named files in different
    subfolders can't collide.
    """
    dataroom = dataroom or root.name
    classifier = classifier or Classifier()
    inv = scan_folder(root)

    result = IngestResult(
        dataroom=dataroom,
        unsupported=[p.as_posix() for p in inv.unsupported],
        ignored=inv.ignored)

    done = _docs_with_facts(conn, dataroom, REAL_TIER) if resume else set()
    for rel in inv.pdfs:
        source_doc = rel.as_posix()
        if source_doc in done:
            result.skipped += 1
            continue
        doc_type = classifier.classify(root / rel)
        if doc_type is None:
            result.unclassified.append(source_doc)
            continue
        try:
            data = extractor.extract(root / rel, doc_type)
            facts = build_facts(doc_type, data, dataroom=dataroom,
                                tier=REAL_TIER, source_doc=source_doc,
                                extractor=extractor.name)
        except Exception as exc:  # noqa: BLE001 — a bad doc must not kill the run
            result.failures.append(f"{source_doc}: {exc}")
            continue
        replace_doc_facts(conn, facts, dataroom=dataroom, tier=REAL_TIER,
                          source_doc=source_doc)
        result.documents += 1
        result.facts += len(facts)
        result.needs_review += sum(1 for f in facts if f.needs_review)
        result.by_type[doc_type] = result.by_type.get(doc_type, 0) + 1
    return result


def _companies_house(company_number: str):
    """Live Companies House client when we can; None degrades the charges
    check to 'skipped', never to a guess."""
    import os

    if not company_number or not os.environ.get("COMPANIES_HOUSE_API_KEY"):
        return None
    from diligence.external import CompaniesHouseClient

    return CompaniesHouseClient()


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    from diligence.extraction.extractor import ClaudeExtractor
    from diligence.facts import connect, init_db
    from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Ingest a real data room (folder or zip) and report")
    parser.add_argument("folder", type=Path, help="folder or .zip of documents")
    parser.add_argument("--company-number", default="",
                        help="Companies House number (enables live "
                             "charges/insolvency checks)")
    parser.add_argument("--company-name", default=None,
                        help="report header; defaults to CH profile or "
                             "folder name")
    parser.add_argument("--dataroom", default=None,
                        help="fact-table name; defaults to folder name")
    parser.add_argument("--model", default=None)
    parser.add_argument("--resume", action="store_true",
                        help="skip documents that already have facts")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--no-report", action="store_true",
                        help="extract only; skip checks and report")
    args = parser.parse_args()

    root = args.folder
    if root.suffix.lower() == ".zip" and root.is_file():
        root = unpack_zip(root)
    if not root.is_dir():
        raise SystemExit(f"Not a folder: {args.folder}")

    conn = connect()
    init_db(conn)
    extractor = ClaudeExtractor(model=args.model)
    result = ingest_folder(conn, extractor, root, dataroom=args.dataroom,
                           resume=args.resume,
                           classifier=Classifier(model=args.model))

    types = ", ".join(f"{t}×{n}" for t, n in sorted(result.by_type.items()))
    print(f"{result.dataroom}: {result.documents} docs extracted "
          f"({types or 'none'}), {result.skipped} skipped, "
          f"{result.facts} facts ({result.needs_review} below "
          f"{CONFIDENCE_REVIEW_THRESHOLD} confidence, flagged for review)")
    u = extractor.usage
    print(f"API usage: {u.calls} calls, {u.input_tokens:,} in / "
          f"{u.output_tokens:,} out tokens, ~${u.cost_usd:.2f}")
    for failure in result.failures:
        print(f"FAILED: {failure}")
    for name in result.unclassified:
        print(f"UNRECOGNISED (not extracted): {name}")
    for name in result.unsupported:
        print(f"UNSUPPORTED FORMAT (not extracted): {name}")
    if result.ignored:
        print(f"(ignored {result.ignored} OS junk file(s))")

    if args.no_report:
        conn.close()
        return

    from diligence.facts.db import fetch_facts, row_to_fact
    from diligence.report.generate import build_report

    rows = fetch_facts(conn, result.dataroom, REAL_TIER)
    facts = [row_to_fact(r) for r in rows]
    conn.close()
    if not facts:
        raise SystemExit("No facts extracted — nothing to report on.")

    company_name = args.company_name
    ch = None
    try:
        ch = _companies_house(args.company_number)
        if ch is not None and company_name is None:
            profile = ch.profile(args.company_number)
            company_name = profile.company_name if profile else None
    except Exception as exc:  # noqa: BLE001 — CH down must not block the report
        print(f"Companies House unavailable ({exc}); charges check skipped")
        ch = None
    if ch is None and args.company_number:
        print("Note: set COMPANIES_HOUSE_API_KEY to enable the live "
              "charges register check")

    path = build_report(
        facts, claims=[], companies_house=ch,
        company_name=company_name or root.name,
        company_number=args.company_number,
        dataroom=result.dataroom, tier=REAL_TIER, out_dir=args.out,
        needs_review=sum(1 for f in facts if f.needs_review))
    print(f"Report written: {path}")


if __name__ == "__main__":
    main()
