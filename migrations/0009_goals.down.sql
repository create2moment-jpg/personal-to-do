-- Reverts 0009.
DROP INDEX IF EXISTS ix_tasks_goal;
ALTER TABLE tasks DROP COLUMN goal_id;
DROP TABLE IF EXISTS goal_projects;
DROP TABLE IF EXISTS goal_expectations;
DROP TABLE IF EXISTS goals;
