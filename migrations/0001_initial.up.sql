-- 0001 initial schema: projects, tasks, notes (+versions), links, daily plans,
-- audit log and a full-text search index maintained by triggers.
-- Timestamps are ISO-8601 UTC strings; dates are ISO-8601 local calendar days.

CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    area        TEXT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    color       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_projects_name ON projects (lower(name));

CREATE TABLE tasks (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    notes            TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL CHECK (status IN ('backlog', 'planned', 'in_progress', 'blocked', 'done')),
    priority         INTEGER NOT NULL DEFAULT 4 CHECK (priority BETWEEN 1 AND 4),
    estimate_minutes INTEGER CHECK (estimate_minutes IS NULL OR estimate_minutes >= 0),
    actual_minutes   INTEGER NOT NULL DEFAULT 0 CHECK (actual_minutes >= 0),
    project_id       TEXT REFERENCES projects (id) ON DELETE SET NULL,
    area             TEXT,
    parent_id        TEXT REFERENCES tasks (id) ON DELETE CASCADE,
    tags             TEXT NOT NULL DEFAULT '[]',  -- JSON array of normalised tags
    due_date         TEXT,
    scheduled_date   TEXT,
    recurrence       TEXT,
    position         REAL NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    completed_at     TEXT
);
CREATE INDEX ix_tasks_scheduled ON tasks (scheduled_date, status, position);
CREATE INDEX ix_tasks_status ON tasks (status, position);
CREATE INDEX ix_tasks_project ON tasks (project_id);
CREATE INDEX ix_tasks_parent ON tasks (parent_id);
CREATE INDEX ix_tasks_completed ON tasks (completed_at);

CREATE TABLE task_dependencies (
    task_id    TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    depends_on TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on),
    CHECK (task_id <> depends_on)
);

CREATE TABLE notes (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    body             TEXT NOT NULL DEFAULT '',
    kind             TEXT NOT NULL DEFAULT 'general',
    project_id       TEXT REFERENCES projects (id) ON DELETE SET NULL,
    note_date        TEXT,
    tags             TEXT NOT NULL DEFAULT '[]',
    version          INTEGER NOT NULL DEFAULT 1,
    last_snapshot_at TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX ix_notes_kind ON notes (kind, updated_at);
CREATE INDEX ix_notes_date ON notes (note_date);
CREATE UNIQUE INDEX ux_notes_journal_day ON notes (note_date) WHERE kind = 'journal';

CREATE TABLE note_versions (
    note_id    TEXT NOT NULL REFERENCES notes (id) ON DELETE CASCADE,
    version    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (note_id, version)
);

CREATE TABLE links (
    id          TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX ix_links_source ON links (source_type, source_id);
CREATE INDEX ix_links_target ON links (target_type, target_id);

CREATE TABLE daily_plans (
    day                 TEXT PRIMARY KEY,
    capacity_minutes    INTEGER NOT NULL,
    objective           TEXT NOT NULL DEFAULT '',
    top_priority_ids    TEXT NOT NULL DEFAULT '[]',
    review_unfinished   TEXT NOT NULL DEFAULT '',
    review_blockers     TEXT NOT NULL DEFAULT '',
    review_learning     TEXT NOT NULL DEFAULT '',
    review_wins         TEXT NOT NULL DEFAULT '',
    review_tomorrow     TEXT NOT NULL DEFAULT '',
    review_completed_at TEXT,
    updated_at          TEXT
);

-- Append-only audit trail. actor distinguishes user / system / ai changes.
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL CHECK (actor IN ('user', 'system', 'ai')),
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_audit_entity ON audit_log (entity_type, entity_id);
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

-- Derived full-text index (never the source of truth; rebuildable).
CREATE VIRTUAL TABLE search_index USING fts5 (
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    title,
    body,
    tokenize = 'porter unicode61'
);

CREATE TRIGGER tasks_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('task', new.id, new.title, new.description || ' ' || new.notes);
END;
CREATE TRIGGER tasks_au AFTER UPDATE OF title, description, notes ON tasks BEGIN
    DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = old.id;
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('task', new.id, new.title, new.description || ' ' || new.notes);
END;
CREATE TRIGGER tasks_ad AFTER DELETE ON tasks BEGIN
    DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = old.id;
END;

CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('note', new.id, new.title, new.body);
END;
CREATE TRIGGER notes_au AFTER UPDATE OF title, body ON notes BEGIN
    DELETE FROM search_index WHERE entity_type = 'note' AND entity_id = old.id;
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('note', new.id, new.title, new.body);
END;
CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    DELETE FROM search_index WHERE entity_type = 'note' AND entity_id = old.id;
END;
