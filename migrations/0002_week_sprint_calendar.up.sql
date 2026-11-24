-- 0002 Week & Sprint (Phase 2) + Calendar, meetings & time (Phase 3).

-- Workspace-level settings (time zone, working hours, sprint defaults …), JSON values.
CREATE TABLE workspace_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sprints (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    goal           TEXT NOT NULL DEFAULT '',
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'completed')),
    review_summary TEXT NOT NULL DEFAULT '',
    review_lessons TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    completed_at   TEXT,
    CHECK (end_date >= start_date)
);
CREATE INDEX ix_sprints_start ON sprints (start_date);
CREATE UNIQUE INDEX ux_sprints_one_active ON sprints (status) WHERE status = 'active';

ALTER TABLE tasks ADD COLUMN sprint_id TEXT REFERENCES sprints (id) ON DELETE SET NULL;
ALTER TABLE tasks ADD COLUMN commitment TEXT CHECK (commitment IS NULL OR commitment IN ('committed', 'stretch'));
CREATE INDEX ix_tasks_sprint ON tasks (sprint_id);

-- Scope history: every add/remove of a task to a sprint (after_start marks scope change).
CREATE TABLE sprint_scope_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id   TEXT NOT NULL REFERENCES sprints (id) ON DELETE CASCADE,
    task_id     TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('add', 'remove')),
    commitment  TEXT,
    after_start INTEGER NOT NULL DEFAULT 0,
    at          TEXT NOT NULL
);
CREATE INDEX ix_scope_sprint ON sprint_scope_events (sprint_id);

CREATE TABLE weekly_plans (
    week_start          TEXT PRIMARY KEY,  -- Monday (ISO date)
    objectives          TEXT NOT NULL DEFAULT '[]',
    notes               TEXT NOT NULL DEFAULT '',
    review_wins         TEXT NOT NULL DEFAULT '',
    review_lessons      TEXT NOT NULL DEFAULT '',
    review_risks        TEXT NOT NULL DEFAULT '',
    review_next_focus   TEXT NOT NULL DEFAULT '',
    review_completed_at TEXT,
    updated_at          TEXT
);

-- 'auto' = working hours − meetings − buffer; 'manual' = capacity_minutes as set.
ALTER TABLE daily_plans ADD COLUMN capacity_mode TEXT NOT NULL DEFAULT 'auto'
    CHECK (capacity_mode IN ('auto', 'manual'));

CREATE TABLE people (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_people_name ON people (lower(name));

CREATE TABLE topics (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_topics_name ON topics (lower(name));

CREATE TABLE calendar_imports (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    imported_at  TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end   TEXT NOT NULL,
    events       INTEGER NOT NULL,
    series       INTEGER NOT NULL
);

-- One row per recurring meeting (ICS UID). User decisions apply to all occurrences.
CREATE TABLE meeting_series (
    series_key     TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    cadence        TEXT,  -- human-readable, from RRULE
    default_status TEXT NOT NULL DEFAULT 'attending' CHECK (default_status IN ('attending', 'skipped')),
    topic_id       TEXT REFERENCES topics (id) ON DELETE SET NULL,
    rating         INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    notes          TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL
);

-- Imported columns: title, start_at, end_at, all_day, location, organizer, cancelled.
-- User columns (never touched by re-import): status, attended_minutes, rating, note, topic_id.
CREATE TABLE meetings (
    id               TEXT PRIMARY KEY,
    source           TEXT NOT NULL CHECK (source IN ('ics', 'manual')),
    external_key     TEXT,
    series_key       TEXT REFERENCES meeting_series (series_key) ON DELETE SET NULL,
    kind             TEXT NOT NULL DEFAULT 'meeting' CHECK (kind IN ('meeting', 'call')),
    title            TEXT NOT NULL,
    start_at         TEXT NOT NULL,  -- UTC ISO-8601
    end_at           TEXT NOT NULL,
    all_day          INTEGER NOT NULL DEFAULT 0,
    location         TEXT,
    organizer        TEXT,
    cancelled        INTEGER NOT NULL DEFAULT 0,
    status           TEXT CHECK (status IS NULL OR status IN ('attended', 'skipped', 'partial')),
    attended_minutes INTEGER CHECK (attended_minutes IS NULL OR attended_minutes >= 0),
    rating           INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    note             TEXT NOT NULL DEFAULT '',
    topic_id         TEXT REFERENCES topics (id) ON DELETE SET NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    CHECK (end_at >= start_at)
);
CREATE UNIQUE INDEX ux_meetings_external ON meetings (external_key) WHERE external_key IS NOT NULL;
CREATE INDEX ix_meetings_start ON meetings (start_at);
CREATE INDEX ix_meetings_series ON meetings (series_key);

CREATE TABLE meeting_people (
    meeting_id TEXT NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    person_id  TEXT NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    PRIMARY KEY (meeting_id, person_id)
);
CREATE INDEX ix_meeting_people_person ON meeting_people (person_id);
