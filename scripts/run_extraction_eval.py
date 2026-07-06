"""Resume-and-score runner for the live extraction eval (issue #8)."""

import sys
from pathlib import Path

from dotenv import load_dotenv

from diligence.evals.ground_truth import expected_facts
from diligence.evals.scoring import score_extraction
from diligence.extraction.extractor import ClaudeExtractor
from diligence.extraction.pipeline import extract_dataroom
from diligence.facts import connect, init_db
from diligence.facts.db import fetch_facts, row_to_fact

load_dotenv()
ROOM = Path("data_rooms/copper_kettle_clean")
TIERS = ("clean", "scanned", "photographed")


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None,
                        help="extraction model (default: env/Opus)")
    parser.add_argument("--label", default=ROOM.name,
                        help="dataroom label in the fact table (use a "
                             "distinct label to keep other models' results)")
    args = parser.parse_args()

    conn = connect()
    init_db(conn)
    extractor = ClaudeExtractor(model=args.model)
    log(f"model={extractor.model} label={args.label}")

    for tier in TIERS:
        result = extract_dataroom(conn, extractor, ROOM, tier,
                                  dataroom=args.label, resume=True)
        log(f"EXTRACTED {tier}: {result.documents} new, "
            f"{result.skipped} skipped, {len(result.failures)} failures")
        for failure in result.failures:
            log(f"  FAIL {failure}")

    from diligence.dataroom.spec import build_spec
    from diligence.ledger import generate_ledger

    expected = expected_facts(build_spec(generate_ledger()),
                              dataroom=args.label)
    exit_ok = True
    for tier in TIERS:
        extracted = [row_to_fact(r) for r in fetch_facts(conn, args.label, tier)]
        report = score_extraction(expected, extracted, tier=tier)
        log("")
        log(report.table())
        for score in report.by_doc_type.values():
            for miss in score.mismatches[:4]:
                log(f"    MISS {miss}")
        if tier == "clean":
            for doc_type, s in report.by_doc_type.items():
                if s.accuracy < 0.95:
                    exit_ok = False
                    log(f"  BELOW EXIT CRITERION: {doc_type} {s.accuracy:.1%}")
        if tier == "scanned" and report.overall < 0.85:
            log(f"  KILL CRITERION WARNING: scanned {report.overall:.1%} < 85%")

    u = extractor.usage
    log(f"\nAPI usage this run: {u.calls} calls, {u.input_tokens:,} in / "
        f"{u.output_tokens:,} out, ~${u.cost_usd:.2f}")
    log("RESULT: " + ("EXIT CRITERION MET" if exit_ok else "EXIT CRITERION NOT MET"))
    conn.close()
    return 0 if exit_ok else 1


if __name__ == "__main__":
    sys.exit(main())
