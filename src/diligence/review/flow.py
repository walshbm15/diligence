"""Human verification of quarantined facts (golden rule 4's mechanism).

Low-confidence facts never enter checks. A reviewer looks at the cited
page and either accepts the machine's reading, corrects it, or marks the
figure unreadable. Resolutions create NEW facts (extractor='human',
confidence 1.0) and the original extraction stays in place, flagged as
reviewed — a full audit trail of machine reading vs human judgement.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from diligence.facts.model import CONFIDENCE_REVIEW_THRESHOLD

VALID_ACTIONS = ("accept", "correct", "unreadable")


def render_cited_page(room_dir: Path, tier: str, source_doc: str, page: int,
                      out_dir: Path) -> Path | None:
    """Render the cited page to PNG so the reviewer can look at it."""
    import pypdfium2 as pdfium

    pdf_path = room_dir / tier / source_doc
    if not pdf_path.exists():
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{Path(source_doc).stem}_p{page}.png"
    if not out.exists():
        doc = pdfium.PdfDocument(str(pdf_path))
        index = min(max(page, 1), len(doc)) - 1
        doc[index].render(scale=200 / 72).to_pil().save(str(out))
        doc.close()
    return out


def resolve_fact(conn, fact_row: dict, action: str,
                 corrected_pence: int | None = None,
                 reviewer: str = "human") -> int | None:
    """Resolve one quarantined fact. Returns the new human fact id, if any.

    - accept: the machine's value was right — promote it at confidence 1.0
    - correct: insert the reviewer's value at confidence 1.0
    - unreadable: no usable figure exists; nothing enters the checks
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {VALID_ACTIONS}")
    if action == "correct" and corrected_pence is None:
        raise ValueError("correct requires a value")

    resolution = {"reviewed": True, "resolution": action,
                  "reviewed_at": dt.datetime.now(dt.UTC).isoformat()}
    conn.execute("UPDATE fact SET attrs = attrs || %s::jsonb WHERE id = %s",
                 (json.dumps(resolution), fact_row["id"]))

    new_id = None
    if action in ("accept", "correct"):
        value_pence = (fact_row["value_pence"] if action == "accept"
                       else corrected_pence)
        attrs = dict(fact_row.get("attrs") or {})
        attrs.pop("reviewed", None)
        attrs.pop("resolution", None)
        attrs["original_fact_id"] = fact_row["id"]
        row = conn.execute(
            """
            INSERT INTO fact (dataroom, tier, doc_type, fact_type,
                              value_pence, value_num, value_text, value_date,
                              period_start, period_end, attrs,
                              source_doc, page, bbox, confidence, extractor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, 1.0, %s)
            RETURNING id
            """,
            (fact_row["dataroom"], fact_row["tier"], fact_row["doc_type"],
             fact_row["fact_type"], value_pence, fact_row["value_num"],
             fact_row["value_text"], fact_row["value_date"],
             fact_row["period_start"], fact_row["period_end"],
             json.dumps(attrs), fact_row["source_doc"], fact_row["page"],
             json.dumps(fact_row["bbox"]) if fact_row.get("bbox") else None,
             reviewer)).fetchone()
        new_id = row["id"]
    conn.commit()
    return new_id


def _parse_pounds(text: str) -> int:
    cleaned = text.replace("£", "").replace(",", "").strip()
    return round(float(cleaned) * 100)


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    from diligence.facts import connect, init_db
    from diligence.facts.db import facts_needing_review

    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Review quarantined low-confidence facts")
    parser.add_argument("room_dir", type=Path)
    parser.add_argument("--tier", default="clean")
    parser.add_argument("--list", action="store_true",
                        help="list the queue without reviewing")
    args = parser.parse_args()

    conn = connect()
    init_db(conn)
    queue = facts_needing_review(conn, args.room_dir.name, args.tier,
                                 CONFIDENCE_REVIEW_THRESHOLD)
    if not queue:
        print("Review queue is empty.")
        return
    print(f"{len(queue)} facts awaiting review\n")
    if args.list:
        for row in queue:
            value = (f"£{row['value_pence'] / 100:,.2f}"
                     if row["value_pence"] is not None else row["value_text"]
                     or row["value_num"] or row["value_date"] or "—")
            print(f"  #{row['id']} {row['source_doc']} p{row['page']} "
                  f"{row['fact_type']} = {value} "
                  f"(conf {row['confidence']:.2f})")
        return

    out_dir = Path("output/review")
    for i, row in enumerate(queue, 1):
        png = render_cited_page(args.room_dir, args.tier, row["source_doc"],
                                row["page"], out_dir)
        value = (f"£{row['value_pence'] / 100:,.2f}"
                 if row["value_pence"] is not None else str(
                     row["value_text"] or row["value_num"]
                     or row["value_date"] or "(no value)"))
        print(f"[{i}/{len(queue)}] {row['source_doc']} page {row['page']}")
        print(f"    field: {row['fact_type']}")
        print(f"    machine read: {value} (confidence {row['confidence']:.2f})")
        if png:
            print(f"    page image: {png}")
        choice = input("    [a]ccept / [c]orrect / [u]nreadable / "
                       "[s]kip / [q]uit: ").strip().lower()
        if choice == "q":
            break
        if choice == "s" or not choice:
            continue
        if choice == "a":
            resolve_fact(conn, row, "accept")
        elif choice == "c":
            raw = input("    correct value (£): ")
            resolve_fact(conn, row, "correct",
                         corrected_pence=_parse_pounds(raw))
        elif choice == "u":
            resolve_fact(conn, row, "unreadable")
    remaining = len(facts_needing_review(conn, args.room_dir.name, args.tier,
                                         CONFIDENCE_REVIEW_THRESHOLD))
    print(f"\nDone. {remaining} facts still awaiting review.")
    conn.close()


if __name__ == "__main__":
    main()
