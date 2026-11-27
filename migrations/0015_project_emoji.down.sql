-- Reverts 0015. Projects lose only their emoji.
ALTER TABLE projects DROP COLUMN emoji;
