-- 0005 Extracted facts with provenance (AI proposals the user accepts or rejects).

CREATE TABLE fact_runs (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    status          TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    model           TEXT,
    prompt_template TEXT,
    chunks_total    INTEGER NOT NULL DEFAULT 0,
    chunks_done     INTEGER NOT NULL DEFAULT 0,
    facts_found     INTEGER NOT NULL DEFAULT 0,
    facts_dropped   INTEGER NOT NULL DEFAULT 0,   -- failed the verbatim-quote check
    error           TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT
);
CREATE INDEX ix_fact_runs_doc ON fact_runs (document_id, started_at);

CREATE TABLE facts (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_id        TEXT REFERENCES document_chunks (id) ON DELETE SET NULL,
    run_id          TEXT REFERENCES fact_runs (id) ON DELETE SET NULL,
    page            INTEGER,
    section         TEXT,
    kind            TEXT NOT NULL,
    statement       TEXT NOT NULL,
    quote           TEXT NOT NULL,              -- verbatim span of the source chunk
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    epistemic       TEXT NOT NULL DEFAULT 'document_claim',
    status          TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'rejected')),
    model           TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    extractor_version TEXT,
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX ix_facts_doc ON facts (document_id, status);
CREATE INDEX ix_facts_kind ON facts (kind, status);
