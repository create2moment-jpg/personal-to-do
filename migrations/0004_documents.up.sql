-- 0004 Knowledge inbox: original documents (content-hashed files in LOCAL_DATA_DIR),
-- extracted chunks with page provenance, and full-text search over chunks.

CREATE TABLE documents (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    filename          TEXT NOT NULL,
    mime              TEXT NOT NULL,
    sha256            TEXT NOT NULL UNIQUE,
    size_bytes        INTEGER NOT NULL,
    storage_path      TEXT NOT NULL,           -- relative to LOCAL_DATA_DIR
    kind              TEXT NOT NULL DEFAULT 'other',
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'processing', 'ready', 'needs_ocr', 'failed')),
    error             TEXT,
    pages             INTEGER,
    chars             INTEGER,
    extractor_version TEXT,
    supersedes_id     TEXT REFERENCES documents (id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    processed_at      TEXT
);
CREATE INDEX ix_documents_status ON documents (status);

CREATE TABLE document_chunks (
    id                TEXT PRIMARY KEY,
    document_id       TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    seq               INTEGER NOT NULL,
    page_start        INTEGER,
    page_end          INTEGER,
    section           TEXT,
    text              TEXT NOT NULL,
    char_start        INTEGER NOT NULL,
    char_end          INTEGER NOT NULL,
    extractor_version TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    UNIQUE (document_id, seq)
);

CREATE TRIGGER chunks_ai AFTER INSERT ON document_chunks BEGIN
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('chunk', new.id, coalesce(new.section, ''), new.text);
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON document_chunks BEGIN
    DELETE FROM search_index WHERE entity_type = 'chunk' AND entity_id = old.id;
END;
