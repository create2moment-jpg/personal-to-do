-- 0020 People view: a role and 1:1 talking points per person.
CREATE TABLE person_profiles (
    person_id      TEXT PRIMARY KEY REFERENCES people (id) ON DELETE CASCADE,
    role           TEXT NOT NULL DEFAULT '',
    talking_points TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL
);
