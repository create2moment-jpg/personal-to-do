-- Reverts 0008. Occurrences of app-created series stay as standalone manual meetings.
UPDATE meetings SET series_key = NULL
 WHERE series_key IN (SELECT series_key FROM meeting_series WHERE source = 'app');
DELETE FROM meeting_series WHERE source = 'app';
ALTER TABLE meeting_series DROP COLUMN plan;
ALTER TABLE meeting_series DROP COLUMN source;
