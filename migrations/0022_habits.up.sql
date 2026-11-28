-- 0022 Habits (B-030): small daily or weekly habits and the days they were done.
CREATE TABLE habits (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    emoji       TEXT,
    cadence     TEXT NOT NULL DEFAULT 'daily' CHECK (cadence IN ('daily', 'weekdays', 'weekly')),
    archived    INTEGER NOT NULL DEFAULT 0,
    position    REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE habit_checks (
    habit_id  TEXT NOT NULL REFERENCES habits (id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    PRIMARY KEY (habit_id, day)
);
