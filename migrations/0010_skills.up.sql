-- 0010 Skills matrix: self-ratings with history, targets, evidence from accepted
-- facts (user-confirmed links), and goals that grow a skill.

CREATE TABLE skills (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'General',
    description  TEXT NOT NULL DEFAULT '',
    target_level INTEGER CHECK (target_level IS NULL OR target_level BETWEEN 1 AND 5),
    position     REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_skills_name ON skills (lower(name));

CREATE TABLE skill_ratings (
    id       TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    level    INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
    note     TEXT NOT NULL DEFAULT '',
    rated_at TEXT NOT NULL
);
CREATE INDEX ix_skill_ratings ON skill_ratings (skill_id, rated_at);

CREATE TABLE skill_evidence (
    skill_id   TEXT NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    fact_id    TEXT NOT NULL REFERENCES facts (id) ON DELETE CASCADE,
    origin     TEXT NOT NULL CHECK (origin IN ('user', 'suggestion')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (skill_id, fact_id)
);

CREATE TABLE goal_skills (
    goal_id  TEXT NOT NULL REFERENCES goals (id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills (id) ON DELETE CASCADE,
    PRIMARY KEY (goal_id, skill_id)
);
