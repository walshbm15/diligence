-- MIRROR of src/diligence/facts/db.py SCHEMA — Python owns this schema
-- until issue #29 transfers write/schema ownership to this service.
-- Any change here must be byte-equivalent to the Python DDL, or made in
-- Python first. IF NOT EXISTS is deliberate: in dev this API attaches to
-- a database the Python pipeline may already have initialised.

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
