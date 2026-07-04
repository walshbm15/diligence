"""Extraction pipeline: data room tier directory -> fact table."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from diligence.extraction.facts_builder import build_facts, doc_type_for
from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD


@dataclass
class ExtractionResult:
    dataroom: str
    tier: str
    documents: int = 0
    skipped: int = 0
    facts: int = 0
    needs_review: int = 0
    failures: list[str] = field(default_factory=list)


def _docs_with_facts(conn, dataroom: str, tier: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT source_doc FROM fact WHERE dataroom=%s AND tier=%s",
        (dataroom, tier)).fetchall()
    return {r["source_doc"] for r in rows}


def extract_dataroom(conn, extractor, room_dir: Path, tier: str,
                     dataroom: str | None = None,
                     resume: bool = False) -> ExtractionResult:
    """Extract every PDF in `room_dir/tier` into the fact table.

    Idempotent per document (each doc's prior facts are replaced). With
    `resume=True`, documents that already have facts are skipped — for
    re-running after partial failures without re-paying for the rest.
    """
    from diligence.facts.db import insert_facts

    dataroom = dataroom or room_dir.name
    tier_dir = room_dir / tier
    result = ExtractionResult(dataroom=dataroom, tier=tier)

    done = _docs_with_facts(conn, dataroom, tier) if resume else set()
    for pdf in sorted(tier_dir.glob("*.pdf")):
        doc_type = doc_type_for(pdf.name)
        if doc_type is None:
            continue
        if pdf.name in done:
            result.skipped += 1
            continue
        try:
            data = extractor.extract(pdf, doc_type)
            facts = build_facts(doc_type, data, dataroom=dataroom, tier=tier,
                                source_doc=pdf.name, extractor=extractor.name)
        except Exception as exc:  # noqa: BLE001 — a bad doc must not kill the run
            result.failures.append(f"{pdf.name}: {exc}")
            continue
        conn.execute(
            "DELETE FROM fact WHERE dataroom=%s AND tier=%s AND source_doc=%s",
            (dataroom, tier, pdf.name))
        insert_facts(conn, facts)
        result.documents += 1
        result.facts += len(facts)
        result.needs_review += sum(1 for f in facts if f.needs_review)
    return result


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    from diligence.extraction.extractor import ClaudeExtractor
    from diligence.facts import connect, init_db

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("room_dir", type=Path)
    parser.add_argument("--tier", default="clean")
    parser.add_argument("--model", default=None)
    parser.add_argument("--resume", action="store_true",
                        help="skip documents that already have facts")
    args = parser.parse_args()

    conn = connect()
    init_db(conn)
    extractor = ClaudeExtractor(model=args.model)
    result = extract_dataroom(conn, extractor, args.room_dir, args.tier,
                              resume=args.resume)
    u = extractor.usage
    print(f"{result.dataroom}/{result.tier}: {result.documents} docs "
          f"({result.skipped} skipped), {result.facts} facts "
          f"({result.needs_review} below {CONFIDENCE_REVIEW_THRESHOLD} "
          f"confidence, flagged for review)")
    print(f"API usage: {u.calls} calls, {u.input_tokens:,} in / "
          f"{u.output_tokens:,} out tokens, ~${u.cost_usd:.2f}")
    for failure in result.failures:
        print(f"FAILED: {failure}")
    conn.close()


if __name__ == "__main__":
    main()
