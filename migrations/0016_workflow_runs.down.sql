-- Reverts 0016. Workflow run history is removed; nothing else changes.
DROP INDEX IF EXISTS ix_workflow_runs_created;
DROP TABLE IF EXISTS workflow_runs;
