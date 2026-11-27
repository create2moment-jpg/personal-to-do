-- 0009 Goals: year → quarter → month hierarchy, linked to tasks, projects and
-- career expectations. Progress is computed, never stored (except manual/metric input).

CREATE TABLE goals (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    horizon         TEXT NOT NULL CHECK (horizon IN ('year', 'quarter', 'month')),
    period          TEXT NOT NULL,            -- '2026', '2026-Q4', '2026-11'
    parent_id       TEXT REFERENCES goals (id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'achieved', 'paused', 'dropped')),
    progress_mode   TEXT NOT NULL DEFAULT 'auto' CHECK (progress_mode IN ('auto', 'manual', 'metric')),
    manual_progress INTEGER CHECK (manual_progress IS NULL OR manual_progress BETWEEN 0 AND 100),
    metric_unit     TEXT,
    metric_start    REAL,
    metric_target   REAL,
    metric_current  REAL,
    emoji           TEXT,
    position        REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    achieved_at     TEXT
);
CREATE INDEX ix_goals_period ON goals (horizon, period, position);
CREATE INDEX ix_goals_parent ON goals (parent_id);

CREATE TABLE goal_expectations (
    goal_id        TEXT NOT NULL REFERENCES goals (id) ON DELETE CASCADE,
    expectation_id TEXT NOT NULL REFERENCES career_expectations (id) ON DELETE CASCADE,
    PRIMARY KEY (goal_id, expectation_id)
);

CREATE TABLE goal_projects (
    goal_id    TEXT NOT NULL REFERENCES goals (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    PRIMARY KEY (goal_id, project_id)
);

ALTER TABLE tasks ADD COLUMN goal_id TEXT REFERENCES goals (id) ON DELETE SET NULL;
CREATE INDEX ix_tasks_goal ON tasks (goal_id);
