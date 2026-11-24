-- Reverts 0001. Destroys all data: the migrate tool takes a backup first.
DROP TRIGGER IF EXISTS notes_ad;
DROP TRIGGER IF EXISTS notes_au;
DROP TRIGGER IF EXISTS notes_ai;
DROP TRIGGER IF EXISTS tasks_ad;
DROP TRIGGER IF EXISTS tasks_au;
DROP TRIGGER IF EXISTS tasks_ai;
DROP TABLE IF EXISTS search_index;
DROP TRIGGER IF EXISTS audit_log_no_update;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS daily_plans;
DROP TABLE IF EXISTS links;
DROP TABLE IF EXISTS note_versions;
DROP TABLE IF EXISTS notes;
DROP TABLE IF EXISTS task_dependencies;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS projects;
