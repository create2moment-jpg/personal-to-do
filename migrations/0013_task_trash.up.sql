-- 0013 Undoable deletes: a deleted task goes to the trash (deleted_at) for 30 days.
ALTER TABLE tasks ADD COLUMN deleted_at TEXT;
CREATE INDEX ix_tasks_deleted ON tasks (deleted_at);

-- Keep trashed tasks out of search; put them back when restored.
DROP TRIGGER tasks_au;
CREATE TRIGGER tasks_au AFTER UPDATE OF title, description, notes ON tasks WHEN new.deleted_at IS NULL BEGIN
    DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = old.id;
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('task', new.id, new.title, new.description || ' ' || new.notes);
END;
CREATE TRIGGER tasks_trash AFTER UPDATE OF deleted_at ON tasks
WHEN new.deleted_at IS NOT NULL AND old.deleted_at IS NULL BEGIN
    DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = old.id;
END;
CREATE TRIGGER tasks_untrash AFTER UPDATE OF deleted_at ON tasks
WHEN new.deleted_at IS NULL AND old.deleted_at IS NOT NULL BEGIN
    INSERT INTO search_index (entity_type, entity_id, title, body)
    VALUES ('task', new.id, new.title, new.description || ' ' || new.notes);
END;
