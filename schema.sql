-- Recall Phase 0 schema.
-- Load this in the CockroachDB SQL Shell (or: cockroach sql --url "$DATABASE_URL" < schema.sql)
-- before running phase0_smoke_test.py.

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY,
    name STRING NOT NULL,
    domain STRING NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type STRING NOT NULL,
    entity_id UUID NOT NULL REFERENCES companies (id),
    fact_text STRING NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
