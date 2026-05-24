# =============================================================================
# alembic/env.py — Alembic migration environment
# Tradie Platform
# =============================================================================
#
# DRIVER STRATEGY:
#   FastAPI  → asyncpg  (async, high performance for API requests)
#   Alembic  → psycopg2 (sync, standard, handles all SQL including multi-statement)
#
# WHY NOT ASYNC ALEMBIC:
#   asyncpg has a known limitation — it cannot execute multiple SQL statements
#   in a single op.execute() call. Several migration files in this project use
#   op.execute() with CREATE TABLE + CREATE INDEX in one string.
#   psycopg2 handles this without any issue.
#
# URL DERIVATION (no extra env var needed):
#   DATABASE_URL = postgresql+asyncpg://user:pass@host/db
#   Sync URL     = postgresql://user:pass@host/db
#   Derived by:  DATABASE_URL.replace("+asyncpg", "")
# =============================================================================

import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import Base

# =============================================================================
# Import all models — required for autogenerate to detect schema changes.
# =============================================================================

# =============================================================================
# Alembic config
# =============================================================================

config = context.config

# Derive the psycopg2 (sync) URL from DATABASE_URL.
# DATABASE_URL uses asyncpg for FastAPI. Alembic needs the plain psycopg2 URL.
# We just remove "+asyncpg" from the driver — same host, user, password, DB.
_database_url = os.getenv("DATABASE_URL", "")
if not _database_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Alembic cannot connect to the database."
    )

# postgresql+asyncpg://... → postgresql://...
_sync_url = _database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", _sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# =============================================================================
# PostGIS tables — skip in migrations
# =============================================================================

POSTGIS_TABLES = {
    "spatial_ref_sys", "geometry_columns", "geography_columns",
    "raster_columns", "raster_overviews", "pagc_lex", "pagc_gaz",
    "pagc_rules", "topology", "layer", "geocode_settings",
    "geocode_settings_default", "direction_lookup", "secondary_unit_lookup",
    "state_lookup", "street_type_lookup", "place_lookup", "county_lookup",
    "countysub_lookup", "zip_lookup", "zip_lookup_all", "zip_lookup_base",
    "zip_state", "zip_state_loc", "county", "state", "place", "cousub",
    "edges", "addrfeat", "faces", "loader_platform", "loader_variables",
    "loader_lookuptables", "addr", "featnames", "bg", "tabblock",
    "tabblock20", "tract", "zcta5", "zcta520",
}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in POSTGIS_TABLES:
        return False
    return True


# =============================================================================
# Offline migrations
# =============================================================================

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# =============================================================================
# Online migrations — synchronous psycopg2
# =============================================================================

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


# =============================================================================
# Entry point
# =============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
