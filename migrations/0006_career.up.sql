-- 0006 Career: level expectations (from accepted framework facts or entered by hand)
-- and evidence links from accepted facts to expectations.

CREATE TABLE career_expectations (
    id             TEXT PRIMARY KEY,
    level          TEXT NOT NULL,
    text           TEXT NOT NULL,
    competency     TEXT,
    source_fact_id TEXT UNIQUE REFERENCES facts (id) ON DELETE SET NULL,
    position       REAL NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX ix_expectations_level ON career_expectations (level, position);

CREATE TABLE evidence_links (
    id             TEXT PRIMARY KEY,
    expectation_id TEXT NOT NULL REFERENCES career_expectations (id) ON DELETE CASCADE,
    fact_id        TEXT NOT NULL REFERENCES facts (id) ON DELETE CASCADE,
    origin         TEXT NOT NULL CHECK (origin IN ('user', 'suggestion')),
    score          REAL,
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    UNIQUE (expectation_id, fact_id)
);
