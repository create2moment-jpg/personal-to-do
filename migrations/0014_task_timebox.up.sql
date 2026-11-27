-- 0014 Timeboxing: a planned task can hold a start time ("HH:MM", local) on its day.
ALTER TABLE tasks ADD COLUMN timebox_start TEXT;
CREATE INDEX ix_tasks_timebox ON tasks (scheduled_date, timebox_start);
