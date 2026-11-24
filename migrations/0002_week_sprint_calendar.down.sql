-- Reverts 0002. The migrate tool takes a backup first.
DROP TABLE IF EXISTS meeting_people;
DROP TABLE IF EXISTS meetings;
DROP TABLE IF EXISTS meeting_series;
DROP TABLE IF EXISTS calendar_imports;
DROP TABLE IF EXISTS topics;
DROP TABLE IF EXISTS people;
ALTER TABLE daily_plans DROP COLUMN capacity_mode;
DROP TABLE IF EXISTS weekly_plans;
DROP TABLE IF EXISTS sprint_scope_events;
DROP INDEX IF EXISTS ix_tasks_sprint;
ALTER TABLE tasks DROP COLUMN commitment;
ALTER TABLE tasks DROP COLUMN sprint_id;
DROP INDEX IF EXISTS ux_sprints_one_active;
DROP INDEX IF EXISTS ix_sprints_start;
DROP TABLE IF EXISTS sprints;
DROP TABLE IF EXISTS workspace_settings;
