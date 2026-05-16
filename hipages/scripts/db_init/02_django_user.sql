-- =============================================================================
-- scripts/db_init/02_django_user.sql
-- Creates the restricted Django admin database user.
-- Runs automatically on first postgres container startup.
-- =============================================================================
--
-- WHY A SEPARATE USER:
--   Django admin uses the database directly. If an attacker compromises the
--   Django admin session, they should not be able to write to tables that
--   Django admin has no business writing to (e.g. payments, job_events).
--   Principle of least privilege.
--
-- FIX: Was hardcoded to "tradie_production" which doesn't exist in dev.
--      Now uses current_database() — works in dev AND production with zero
--      changes. Postgres runs this script inside the database it just created,
--      so current_database() always returns the right name.
-- =============================================================================

-- Create the user if it doesn't already exist.
-- Password is a placeholder — replace via environment in production.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'tradie_admin_ro'
    ) THEN
        CREATE USER tradie_admin_ro WITH PASSWORD 'PLACEHOLDER_REPLACED_BY_INIT_SCRIPT';
    END IF;
END
$$;

-- FIX: Use current_database() instead of hardcoded 'tradie_production'
-- This runs inside whichever DB postgres just created:
--   dev  → tradie_dev
--   prod → tradie_production
-- Both work with zero changes to this file.
DO $$
BEGIN
    EXECUTE 'GRANT CONNECT ON DATABASE ' || current_database() || ' TO tradie_admin_ro';
END
$$;

GRANT USAGE ON SCHEMA public TO tradie_admin_ro;

-- =============================================================================
-- READ access to all tables (SELECT only).
-- Applied after Alembic creates tables — run this in deploy.sh after migrations:
--
--   psql -U tradie -d tradie_production \
--     -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO tradie_admin_ro;"
--   psql -U tradie -d tradie_production \
--     -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public
--         GRANT SELECT ON TABLES TO tradie_admin_ro;"
-- =============================================================================

-- =============================================================================
-- WRITE access — only tables Django admin must manage.
-- Applied after Alembic in deploy.sh:
--
--   GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
--     tradie_verifications,
--     disputes,
--     admin_notes,
--     skill_categories
--   TO tradie_admin_ro;
--
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tradie_admin_ro;
-- =============================================================================