-- =============================================================================
-- fix_existing_job_statuses.sql
--
-- One-time fix: jobs that already have leads distributed but are still "open"
-- should be "quoted" so the homeowner accept flow works correctly.
--
-- Run inside Docker:
--   docker exec -it tradie_dev_fastapi \
--     psql $DATABASE_URL -f scripts/fix_existing_job_statuses.sql
-- =============================================================================

-- Move "open" jobs that have at least one lead to "quoted"
UPDATE jobs
SET    status = 'quoted'
WHERE  status = 'open'
AND    id IN (
    SELECT DISTINCT job_id FROM leads
);

SELECT
    COUNT(*) FILTER (WHERE status = 'quoted') AS jobs_now_quoted,
    COUNT(*) FILTER (WHERE status = 'open')   AS jobs_still_open
FROM jobs
WHERE is_deleted = false;
