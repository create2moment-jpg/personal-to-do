-- 0012 Local embeddings for search by meaning. Vectors are float32, unit length,
-- computed on this machine by your own model; text hash detects stale entries.
CREATE TABLE embeddings (
    key        TEXT PRIMARY KEY,   -- "<kind>:<id>", e.g. note:abc, chunk:def
    model      TEXT NOT NULL,
    text_hash  TEXT NOT NULL,
    dim        INTEGER NOT NULL,
    vector     BLOB NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX ix_embeddings_model ON embeddings (model);
