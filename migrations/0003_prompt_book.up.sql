-- 0003 Prompt Book: books with an arbitrary-depth tree of chapters/sections and pages,
-- page versions (original / edited / ai / used), and full-text search over pages.

CREATE TABLE books (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    emoji       TEXT,
    description TEXT NOT NULL DEFAULT '',
    position    REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Containers (chapter/section) nest freely; pages are leaves holding the prompt text.
CREATE TABLE book_nodes (
    id           TEXT PRIMARY KEY,
    book_id      TEXT NOT NULL REFERENCES books (id) ON DELETE CASCADE,
    parent_id    TEXT REFERENCES book_nodes (id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('chapter', 'section', 'page')),
    title        TEXT NOT NULL,
    emoji        TEXT,
    body         TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',
    position     REAL NOT NULL DEFAULT 0,
    version      INTEGER NOT NULL DEFAULT 1,
    use_count    INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    rating       INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX ix_book_nodes_tree ON book_nodes (book_id, parent_id, position);

CREATE TABLE prompt_versions (
    node_id         TEXT NOT NULL REFERENCES book_nodes (id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    body            TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('original', 'edited', 'ai', 'used', 'restored')),
    model           TEXT,
    prompt_template TEXT,
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (node_id, version)
);

CREATE TRIGGER book_pages_ai AFTER INSERT ON book_nodes WHEN new.kind = 'page' BEGIN
    INSERT INTO search_index (entity_type, entity_id, title, body) VALUES ('page', new.id, new.title, new.body);
END;
CREATE TRIGGER book_pages_au AFTER UPDATE OF title, body ON book_nodes WHEN new.kind = 'page' BEGIN
    DELETE FROM search_index WHERE entity_type = 'page' AND entity_id = old.id;
    INSERT INTO search_index (entity_type, entity_id, title, body) VALUES ('page', new.id, new.title, new.body);
END;
CREATE TRIGGER book_pages_ad AFTER DELETE ON book_nodes WHEN old.kind = 'page' BEGIN
    DELETE FROM search_index WHERE entity_type = 'page' AND entity_id = old.id;
END;
