"""Postgres persistence for the fact table."""

from __future__ import annotations

import datetime as dt
import json
import os

import psycopg
from psycopg.rows import dict_row

from diligence.facts.model import Fact

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact (
    id BIGSERIAL PRIMARY KEY,
    dataroom TEXT NOT NULL,
    tier TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    value_pence BIGINT,
    value_num DOUBLE PRECISION,
    value_text TEXT,
    value_date DATE,
    period_start DATE,
    period_end DATE,
    attrs JSONB NOT NULL DEFAULT '{}',
    -- Provenance is not optional (golden rule 2)
    source_doc TEXT NOT NULL CHECK (source_doc <> ''),
    page INT NOT NULL CHECK (page >= 1),
    bbox JSONB,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    extractor TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fact_lookup
    ON fact (dataroom, tier, fact_type, period_start);
"""


def database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://diligence:diligence@localhost:5433/diligence")


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)


def init_db(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)
    conn.commit()


def clear_dataroom(conn: psycopg.Connection, dataroom: str,
                   tier: str | None = None) -> None:
    if tier:
        conn.execute("DELETE FROM fact WHERE dataroom = %s AND tier = %s",
                     (dataroom, tier))
    else:
        conn.execute("DELETE FROM fact WHERE dataroom = %s", (dataroom,))
    conn.commit()


def insert_facts(conn: psycopg.Connection, facts: list[Fact]) -> int:
    rows = [(
        f.dataroom, f.tier, f.doc_type, f.fact_type,
        f.value_pence, f.value_num, f.value_text, f.value_date,
        f.period_start, f.period_end, json.dumps(f.attrs),
        f.source_doc, f.page,
        json.dumps(list(f.bbox)) if f.bbox else None,
        f.confidence, f.extractor,
    ) for f in facts]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO fact (dataroom, tier, doc_type, fact_type,
                              value_pence, value_num, value_text, value_date,
                              period_start, period_end, attrs,
                              source_doc, page, bbox, confidence, extractor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
            """, rows)
    conn.commit()
    return len(rows)


def fetch_facts(conn: psycopg.Connection, dataroom: str, tier: str,
                fact_type: str | None = None,
                min_confidence: float = 0.0) -> list[dict]:
    q = ("SELECT * FROM fact WHERE dataroom = %s AND tier = %s "
         "AND confidence >= %s")
    params: list = [dataroom, tier, min_confidence]
    if fact_type:
        q += " AND fact_type = %s"
        params.append(fact_type)
    q += " ORDER BY period_start, source_doc, page, id"
    return conn.execute(q, params).fetchall()


def facts_needing_review(conn: psycopg.Connection, dataroom: str,
                         tier: str, threshold: float) -> list[dict]:
    """Quarantined facts not yet resolved by a human reviewer."""
    return conn.execute(
        "SELECT * FROM fact WHERE dataroom = %s AND tier = %s "
        "AND confidence < %s AND NOT (attrs ? 'reviewed') "
        "ORDER BY source_doc, page, id",
        (dataroom, tier, threshold)).fetchall()


def row_to_fact(row: dict) -> Fact:
    bbox = row.get("bbox")
    return Fact(
        dataroom=row["dataroom"], tier=row["tier"], doc_type=row["doc_type"],
        fact_type=row["fact_type"], source_doc=row["source_doc"],
        page=row["page"], confidence=row["confidence"],
        value_pence=row.get("value_pence"), value_num=row.get("value_num"),
        value_text=row.get("value_text"), value_date=_as_date(row.get("value_date")),
        period_start=_as_date(row.get("period_start")),
        period_end=_as_date(row.get("period_end")),
        attrs=row.get("attrs") or {},
        bbox=tuple(bbox) if bbox else None,
        extractor=row.get("extractor", ""),
    )


def _as_date(v) -> dt.date | None:
    if v is None or isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))
