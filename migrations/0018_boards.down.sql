-- Reverts 0018. Boards and everything on them are removed.
DROP INDEX IF EXISTS ix_board_items_ref;
DROP TABLE IF EXISTS board_items;
DROP TABLE IF EXISTS boards;
