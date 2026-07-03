"""Extraction pipeline: data room tier directory -> fact table."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from diligence.extraction.facts_builder import build_facts, doc_type_for
from diligence.facts.db import clear_dataroom, insert_facts
from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD


@dataclass
class ExtractionResult:
    dataroom: str
    tier: str
    documents: int = 0
    facts: int = 0
    needs_review: int = 0
    failures: list[str] = field(default_factory=list)


def extract_dataroom(conn, extractor, room_dir: Path, tier: str,
                     dataroom: str | None = None) -> ExtractionResult:
    """Extract every PDF in `room_dir/tier` into the fact table."""
    dataroom = dataroom or room_dir.name
    tier_dir = room_dir / tier
    result = ExtractionResult(dataroom=dataroom, tier=tier)

    clear_dataroom(conn, dataroom, tier=tier)
    for pdf in sorted(tier_dir.glob("*.pdf")):
        doc_type = doc_type_for(pdf.name)
        if doc_type is None:
            continue
        try:
            data = extractor.extract(pdf, doc_type)
            facts = build_facts(doc_type, data, dataroom=dataroom, tier=tier,
                                source_doc=pdf.name, extractor=extractor.name)
        except Exception as exc:  # noqa: BLE001 — a bad doc must not kill the run
            result.failures.append(f"{pdf.name}: {exc}")
            continue
        insert_facts(conn, facts)
        result.documents += 1
        result.facts += len(facts)
        result.needs_review += sum(1 for f in facts if f.needs_review)
    return result


def main() -> None:
    import argparse

    from diligence.extraction.extractor import ClaudeExtractor
    from diligence.facts import connect, init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("room_dir", type=Path)
    parser.add_argument("--tier", default="clean")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    conn = connect()
    init_db(conn)
    extractor = ClaudeExtractor(model=args.model)
    result = extract_dataroom(conn, extractor, args.room_dir, args.tier)
    u = extractor.usage
    print(f"{result.dataroom}/{result.tier}: {result.documents} docs, "
          f"{result.facts} facts ({result.needs_review} below "
          f"{CONFIDENCE_REVIEW_THRESHOLD} confidence, flagged for review)")
    print(f"API usage: {u.calls} calls, {u.input_tokens:,} in / "
          f"{u.output_tokens:,} out tokens, ~${u.cost_usd:.2f}")
    for failure in result.failures:
        print(f"FAILED: {failure}")
    conn.close()


if __name__ == "__main__":
    main()
