-- =============================================================================
-- scripts/db_init/02_django_user.sql
-- Creates the restricted Django admin database user.
-- This user has read access to most tables and write access only where needed.
-- =============================================================================
--
-- WHY A SEPARATE USER:
-- Django admin uses the database directly. If an attacker compromises the
-- Django admin session, they should not be able to write to tables that
-- Django admin has no business writing to (e.g. payments, job_events).
-- Principle of least privilege.
-- =============================================================================

-- The password is injected from the environment variable DJANGO_DB_PASSWORD.
-- This SQL runs as the postgres superuser on first DB init.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'tradie_admin_ro'
    ) THEN
        CREATE USER tradie_admin_ro WITH PASSWORD 'PLACEHOLDER_REPLACED_BY_INIT_SCRIPT';
    END IF;
END
$$;

-- Grant connection
GRANT CONNECT ON DATABASE tradie_production TO tradie_admin_ro;
GRANT USAGE ON SCHEMA public TO tradie_admin_ro;

-- Read access to all tables (SELECT only)
-- This is applied after Alembic has created all tables (see deploy.sh).
-- We use a DO block with EXECUTE so it applies to tables created later.
-- In deploy.sh, after alembic upgrade head:
--   docker compose exec postgres psql -U tradie_app -d tradie_production \
--     -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO tradie_admin_ro;"
--   docker compose exec postgres psql -U tradie_app -d tradie_production \
--     -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO tradie_admin_ro;"

-- Write access only to tables Django admin must manage:
-- (Granted after table creation in deploy.sh)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
--   tradie_verifications,
--   disputes,
--   admin_notes,
--   skill_categories
-- TO tradie_admin_ro;

-- Django admin needs sequence access for tables it can insert into.
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tradie_admin_ro;