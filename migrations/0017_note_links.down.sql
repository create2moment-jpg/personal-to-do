-- Reverts 0017. The [[links]] stay in the note text; only the index goes.
DROP INDEX IF EXISTS ix_note_links_target;
DROP INDEX IF EXISTS ix_note_links_source;
DROP TABLE IF EXISTS note_links;
