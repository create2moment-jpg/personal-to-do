-- 0008 Meeting series created in the app (one-off meetings need no schema change).
-- `plan` holds the recurrence, start time, duration and default people/topic as JSON;
-- occurrences are ordinary `meetings` rows (source = 'manual') linked by series_key.
ALTER TABLE meeting_series ADD COLUMN source TEXT NOT NULL DEFAULT 'ics';
ALTER TABLE meeting_series ADD COLUMN plan TEXT;
