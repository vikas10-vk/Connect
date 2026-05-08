# =============================================================================
# alembic/env.py — Async Alembic migration environment
# Tradie Platform
# =============================================================================
#
# FIX APPLIED: execution_options(no_parameters=True)
#
# PROBLEM:
#   asyncpg uses PostgreSQL "extended query protocol" by default.
#   This protocol treats every op.execute() call as a prepared statement.
#   Prepared statements cannot contain multiple SQL commands (e.g. CREATE TABLE
#   followed by CREATE INDEX in the same string).
#   Error: "cannot insert multiple commands into a prepared statement"
#
# FIX:
#   Add execution_options(no_parameters=True) to the migration connection.
#   This switches asyncpg to "simple query protocol" which allows multiple
#   SQL statements in one op.execute() call.
#   This only applies to the Alembic migration connection — FastAPI's
#   connection pool is completely unaffected.
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
# Online migrations — async with no_parameters fix
# =============================================================================

def do_run_migrations(connection):
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
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        connection = await connection.execution_options(no_parameters=True)
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# =============================================================================
# Entry point
# =============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()