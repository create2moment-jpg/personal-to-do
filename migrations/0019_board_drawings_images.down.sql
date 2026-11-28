DELETE FROM search_index WHERE entity_type = 'board';
-- Reverts 0019. Drawings and images are removed from boards (image files stay
-- in the data folder's boards/ directory and can be deleted by hand).
CREATE TABLE board_items_old (
    id          TEXT NOT NULL,
    board_id    TEXT NOT NULL REFERENCES boards (id) ON DELETE CASCADE,
    kind        TEXT NOT NULL
                CHECK (kind IN ('sticky', 'text', 'shape', 'frame', 'connector', 'card')),
    x           REAL NOT NULL DEFAULT 0,
    y           REAL NOT NULL DEFAULT 0,
    w           REAL NOT NULL DEFAULT 0,
    h           REAL NOT NULL DEFAULT 0,
    z           REAL NOT NULL DEFAULT 0,
    text        TEXT NOT NULL DEFAULT '',
    color       TEXT,
    style       TEXT NOT NULL DEFAULT '{}',
    ref_type    TEXT CHECK (ref_type IN ('task', 'note')),
    ref_id      TEXT,
    from_id     TEXT,
    to_id       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (board_id, id)
);
INSERT INTO board_items_old SELECT * FROM board_items WHERE kind NOT IN ('drawing', 'image');
DELETE FROM board_items_old WHERE kind = 'connector' AND (
    from_id NOT IN (SELECT id FROM board_items_old) OR to_id NOT IN (SELECT id FROM board_items_old));
DROP INDEX IF EXISTS ix_board_items_ref;
DROP TABLE board_items;
ALTER TABLE board_items_old RENAME TO board_items;
CREATE INDEX ix_board_items_ref ON board_items (ref_type, ref_id);
