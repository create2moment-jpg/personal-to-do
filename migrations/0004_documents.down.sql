-- Reverts 0004. Original files in LOCAL_DATA_DIR/documents are left untouched.
DROP TRIGGER IF EXISTS chunks_ad;
DROP TRIGGER IF EXISTS chunks_ai;
DELETE FROM search_index WHERE entity_type = 'chunk';
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
