-- Reverts 0014. Tasks keep their day; only the start times are dropped.
DROP INDEX IF EXISTS ix_tasks_timebox;
ALTER TABLE tasks DROP COLUMN timebox_start;
