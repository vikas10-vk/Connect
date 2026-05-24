-- =============================================================================
-- create_job_events_table.sql
--
-- Run this inside Docker to create the job_events audit table:
--
--   docker exec -it tradie_dev_fastapi \
--     psql $DATABASE_URL -f scripts/create_job_events_table.sql
--
-- Safe to run multiple times (uses IF NOT EXISTS / IF NOT EXISTS).
-- =============================================================================

CREATE TABLE IF NOT EXISTS job_events (
    id          BIGSERIAL       PRIMARY KEY,
    job_id      VARCHAR         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    actor_id    VARCHAR         NOT NULL,
    actor_role  VARCHAR(30)     NOT NULL,
    action      VARCHAR(50)     NOT NULL,
    old_value   JSON            DEFAULT NULL,
    new_value   JSON            DEFAULT NULL,
    note        TEXT            DEFAULT NULL,
    ip_address  VARCHAR(45)     DEFAULT NULL,
    created_at  TIMESTAMP       DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id    ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_job_events_created_at ON job_events(created_at);

SELECT 'job_events table ready.' AS status;
