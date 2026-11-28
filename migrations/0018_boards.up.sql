-- 0018 Whiteboards (Miro-style): boards and the items placed on them.
CREATE TABLE boards (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    emoji       TEXT,
    viewport    TEXT NOT NULL DEFAULT '{}',   -- last pan/zoom, JSON
    version     INTEGER NOT NULL DEFAULT 1,   -- bumped on every saved change
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE board_items (
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
    style       TEXT NOT NULL DEFAULT '{}',   -- shape, font size, arrow ends …, JSON
    ref_type    TEXT CHECK (ref_type IN ('task', 'note')),
    ref_id      TEXT,
    from_id     TEXT,                         -- connectors: item ids on the same board
    to_id       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (board_id, id)
);
CREATE INDEX ix_board_items_ref ON board_items (ref_type, ref_id);
