-- Reverts 0013. Trashed tasks are deleted for good first.
DELETE FROM tasks WHERE deleted_at IS NOT NULL;
DROP TRIGGER IF EXISTS tasks_untrash;
DROP TRIGGER IF EXISTS tasks_trash;
DROP TRIGGER IF EXISTS tasks_au;
CREATE TRIGGER tasks_au AFTER UPDATE OF title, description, notes ON tasks BEGIN
    DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = old.id;
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('task', new.id, new.title, new.description || ' ' || new.notes);
END;
DROP INDEX IF EXISTS ix_tasks_deleted;
ALTER TABLE tasks DROP COLUMN deleted_at;
