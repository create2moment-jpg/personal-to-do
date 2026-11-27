-- 0016 Agentic workflows: every run's proposal and what was applied, for audit.
CREATE TABLE workflow_runs (
    id          TEXT PRIMARY KEY,
    workflow    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    actions     TEXT NOT NULL DEFAULT '[]',  -- JSON list of actions with outcomes
    notes       TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'applied', 'dismissed')),
    applied_at  TEXT
);
CREATE INDEX ix_workflow_runs_created ON workflow_runs (created_at);
