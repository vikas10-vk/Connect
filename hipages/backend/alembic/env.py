from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys
from dotenv import load_dotenv
from models.tradie_profile import TradieProfile
from db.session import Base
from models.user import User
from models.tradie_profile import TradieProfile
from models.category import Category
from models.tradie_category import TradieCategory
from models.job import Job
from models.lead import Lead
from models.quote import Quote      
from models.review import Review
from models.job_photo import JobPhoto
from models.inquiry import Inquiry
from models.home_asset import HomeAsset
from models.tradie_pass import TradiePass
from models.tradie_preference import TradiePreference
from models.earnings_record import EarningsRecord
from models.swms_document import SWMSDocument
from models.chat_conversation import ChatConversation
from models.job_assignment import JobAssignment

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True
)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import Base
from models.user import User

config = context.config

config.set_main_option("sqlalchemy.url", os.getenv("SYNC_DATABASE_URL"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ── PostGIS tables to ignore ──────────────────────────────────────
POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
    "place",
    "pagc_lex",
    "pagc_gaz",
    "pagc_rules",
    "topology",
    "layer",
    "geocode_settings",
    "geocode_settings_default",
    "direction_lookup",
    "secondary_unit_lookup",
    "state_lookup",
    "street_type_lookup",
    "place_lookup",
    "county_lookup",
    "countysub_lookup",
    "zip_lookup",
    "zip_lookup_all",
    "zip_lookup_base",
    "zip_state",
    "zip_state_loc",
    "county",
    "state",
    "place",
    "cousub",
    "edges",
    "addrfeat",
    "faces",
    "loader_platform",
    "loader_variables",
    "loader_lookuptables",
    "addr",
    "featnames",
    "bg",
    "tabblock",
    "tabblock20",
    "tract",
    "zcta5",
    "zcta520",
}

def include_object(object, name, type_, reflected, compare_to):
    """Tell Alembic what to include in migrations."""
    if type_ == "table" and name in POSTGIS_TABLES:
        return False   # skip all PostGIS tables
    return True
# ──────────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


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
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()