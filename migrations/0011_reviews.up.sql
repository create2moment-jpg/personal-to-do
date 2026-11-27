-- 0011 Periodic reviews (month, bi-month, quarter, year): your sections plus a
-- snapshot of the numbers they were written against.

CREATE TABLE reviews (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('month', 'bimonth', 'quarter', 'year')),
    period       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'final')),
    highlights   TEXT NOT NULL DEFAULT '',
    challenges   TEXT NOT NULL DEFAULT '',
    learnings    TEXT NOT NULL DEFAULT '',
    next_focus   TEXT NOT NULL DEFAULT '',
    snapshot     TEXT NOT NULL DEFAULT '{}',   -- JSON, computed from your records
    ai_model     TEXT,                         -- set when an AI draft was used
    ai_template  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    finalized_at TEXT,
    UNIQUE (kind, period)
);
