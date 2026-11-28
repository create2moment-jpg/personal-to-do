-- 0017 Wikilinks between notes: one row per [[link]] found in a note's body.
-- Targets are stored as a case-folded title key and resolved by title at read
-- time, so links to notes that do not exist yet ("ghost" notes) work too.
CREATE TABLE note_links (
    source_id  TEXT NOT NULL REFERENCES notes (id) ON DELETE CASCADE,
    target_key TEXT NOT NULL,
    target     TEXT NOT NULL,             -- the title as written
    heading    TEXT,
    alias      TEXT,
    position   INTEGER NOT NULL           -- character offset in the body
);
CREATE INDEX ix_note_links_source ON note_links (source_id);
CREATE INDEX ix_note_links_target ON note_links (target_key);
