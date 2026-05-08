# =============================================================================
# alembic/env.py — Async Alembic migration environment
# Tradie Platform
# =============================================================================
#
# USES ASYNC SQLALCHEMY — no SYNC_DATABASE_URL, no psycopg2 needed.
#
# HOW ASYNC ALEMBIC WORKS:
# Alembic's migration runner (context.run_migrations) is synchronous.
# But our database connection (asyncpg) is async.
# The bridge: conn.run_sync() — runs a sync function inside an async connection.
#
#   asyncio.run(run_async_migrations())
#       └── async with engine.connect() as conn:
#               └── await conn.run_sync(do_run_migrations)
#                       └── context.run_migrations()  ← sync, runs fine here
#
# RESULT: Full async connection, standard Alembic migration runner.
# One DATABASE_URL env var. Same asyncpg driver as your FastAPI app.
# =============================================================================

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import Base

# =============================================================================
# Import all models — required for autogenerate to detect schema changes.
# Add new model imports here as you create them.
# =============================================================================
from models.audit_event import AuditEvent
from models.category import Category
from models.chat_conversation import ChatConversation
from models.earnings_record import EarningsRecord
from models.email_otp import EmailOTP
from models.home_asset import HomeAsset
from models.inquiry import Inquiry
from models.insurance_policy import InsurancePolicy
from models.job import Job
from models.job_assignment import JobAssignment
from models.job_event import JobEvent
from models.job_photo import JobPhoto
from models.lead import Lead
from models.quote import Quote
from models.review import Review
from models.service_question import ServiceQuestion
from models.suburb import Suburb
from models.swms_document import SWMSDocument
from models.team_member import TeamMember
from models.tradie_category import TradieCategory
from models.tradie_certification import TradieCertification
from models.tradie_pass import TradiePass
from models.tradie_preference import TradiePreference
from models.tradie_profile import TradieProfile
from models.user import User

# =============================================================================
# Alembic config
# =============================================================================

config = context.config

# Use DATABASE_URL directly — the asyncpg URL your app already uses.
# No SYNC_DATABASE_URL, no psycopg2, no second env var.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Alembic cannot connect to the database."
    )

config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# =============================================================================
# PostGIS tables — skip in migrations (unchanged from your original)
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
# Offline migrations — generates SQL without connecting to the database.
# Usage: alembic upgrade head --sql > migration.sql
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
# Online migrations — connects to the database and runs migrations.
# =============================================================================

def do_run_migrations(connection):
    """
    The actual migration runner — synchronous.
    Called via conn.run_sync() from inside the async connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations through it.

    NullPool: do not pool connections during migrations.
    Migrations are a one-shot operation — pooling adds no value
    and can cause issues if the process exits without proper cleanup.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync bridges the async connection to the sync migration runner.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs the async function."""
    asyncio.run(run_async_migrations())


# =============================================================================
# Entry point
# =============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()