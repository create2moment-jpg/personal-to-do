-- 0007 Local AI provider settings chosen in the app (one row).
-- Secrets are never stored here: an API key lives in server memory for the
-- session, or is read from an environment variable named in `value`.
CREATE TABLE ai_settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
