-- =============================================================================
-- scripts/db_init/01_extensions.sql
-- Run once when the database is first created.
-- Docker mounts this from ./scripts/db_init/ into the PostgreSQL container.
-- =============================================================================

-- UUID generation — used for all primary keys.
-- uuid_generate_v4() generates a random UUID.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trigram text search — used for fuzzy matching on tradie names, job descriptions.
-- Enables queries like: WHERE name % 'plumbing' (fuzzy match)
-- and GIN indexes on text columns for fast full-text search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Case-insensitive text type — used for email columns so that
-- 'User@Example.com' and 'user@example.com' are treated as the same.
CREATE EXTENSION IF NOT EXISTS citext;

-- PostGIS — geographic queries (tradie within X km of job location).
-- Required for the tradie matching algorithm.
-- NOTE: The postgres:16-alpine image does not include PostGIS.
-- Use postgis/postgis:16-alpine instead in docker-compose if you need this.
-- Uncomment when you add PostGIS to your image:
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- Cryptographic functions — used for pgcrypto-based field encryption as a
-- fallback. Primary encryption happens at the application layer (Fernet).
CREATE EXTENSION IF NOT EXISTS pgcrypto;