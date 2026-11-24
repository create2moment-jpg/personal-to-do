-- Reverts 0003. The migrate tool takes a backup first.
DROP TRIGGER IF EXISTS book_pages_ad;
DROP TRIGGER IF EXISTS book_pages_au;
DROP TRIGGER IF EXISTS book_pages_ai;
DELETE FROM search_index WHERE entity_type = 'page';
DROP TABLE IF EXISTS prompt_versions;
DROP TABLE IF EXISTS book_nodes;
DROP TABLE IF EXISTS books;
