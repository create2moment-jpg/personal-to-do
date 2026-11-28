-- 0019 Boards: freehand drawings and images. SQLite cannot change a CHECK
-- constraint in place, so board_items is rebuilt with the two new kinds.
CREATE TABLE board_items_new (
    id          TEXT NOT NULL,
    board_id    TEXT NOT NULL REFERENCES boards (id) ON DELETE CASCADE,
    kind        TEXT NOT NULL
                CHECK (kind IN ('sticky', 'text', 'shape', 'frame', 'connector', 'card',
                                'drawing', 'image')),
    x           REAL NOT NULL DEFAULT 0,
    y           REAL NOT NULL DEFAULT 0,
    w           REAL NOT NULL DEFAULT 0,
    h           REAL NOT NULL DEFAULT 0,
    z           REAL NOT NULL DEFAULT 0,
    text        TEXT NOT NULL DEFAULT '',   -- drawing: path points; image: stored file name
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
INSERT INTO board_items_new SELECT * FROM board_items;
DROP INDEX IF EXISTS ix_board_items_ref;
DROP TABLE board_items;
ALTER TABLE board_items_new RENAME TO board_items;
CREATE INDEX ix_board_items_ref ON board_items (ref_type, ref_id);

-- B-035: board text in global search (one entry per board).
INSERT INTO search_index (entity_type, entity_id, title, body)
SELECT 'board', b.id, b.title,
       COALESCE((SELECT group_concat(i.text, ' ') FROM board_items i
                 WHERE i.board_id = b.id
                   AND i.kind IN ('sticky', 'text', 'shape', 'frame', 'connector')), '')
FROM boards b;
