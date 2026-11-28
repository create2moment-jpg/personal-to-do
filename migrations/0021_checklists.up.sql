-- 0021 Reusable checklists (B-026): a named list of task lines in capture syntax.
CREATE TABLE checklists (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    lines       TEXT NOT NULL DEFAULT '',   -- one task per line: "Tag the release ~15m !2 #release"
    uses        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
