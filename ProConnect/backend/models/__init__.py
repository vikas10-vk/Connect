# =============================================================================
# models/__init__.py — SQLAlchemy model registry
# Tradie Platform
# =============================================================================
#
# WHY THIS FILE EXISTS:
#   SQLAlchemy resolves relationship string references ("ServiceQuestion",
#   "TradieProfile", etc.) by looking up class names in its registry.
#   The registry only contains models that have already been imported.
#
#   In Celery workers, task modules are imported one at a time. If task A
#   imports Category (which references "ServiceQuestion") but ServiceQuestion
#   hasn't been imported yet, SQLAlchemy raises:
#     InvalidRequestError: failed to locate a name ('ServiceQuestion')
#
#   This file imports every model in dependency order so the ENTIRE registry
#   is populated before any task, query, or mapper configuration runs.
#
# IMPORT ORDER RULE:
#   If model A has relationship("B"), import B before A.
#   service_question must come before category.
#   user must come before everything that references it.
# =============================================================================

# ── Standalone / base models (no foreign model dependencies) ─────────────────
from models.audit_event import AuditEvent  # noqa: F401
from models.category import Category  # noqa: F401
from models.chat_conversation import ChatConversation  # noqa: F401
from models.earnings_record import EarningsRecord  # noqa: F401

# ── User-dependent models ────────────────────────────────────────────────────
from models.email_otp import EmailOTP  # noqa: F401
from models.home_asset import HomeAsset  # noqa: F401
from models.inquiry import Inquiry  # noqa: F401
from models.insurance_policy import InsurancePolicy  # noqa: F401

# ── Job and job-related models ───────────────────────────────────────────────
from models.job import Job  # noqa: F401
from models.job_assignment import JobAssignment  # noqa: F401
from models.job_event import JobEvent  # noqa: F401
from models.job_photo import JobPhoto  # noqa: F401

# ── Transaction models (depend on job + tradie) ──────────────────────────────
from models.lead import Lead  # noqa: F401
from models.outbox_event import OutboxEvent  # noqa: F401
from models.quote import Quote  # noqa: F401
from models.realtime_notification import RealtimeNotification  # noqa: F401
from models.review import Review  # noqa: F401

# ── ServiceQuestion MUST come before Category ────────────────────────────────
# Category.service_questions = relationship("ServiceQuestion", ...)
# If ServiceQuestion is not in the registry when Category mapper configures,
# SQLAlchemy raises InvalidRequestError.
from models.service_question import ServiceQuestion  # noqa: F401
from models.suburb import Suburb  # noqa: F401
from models.team_member import TeamMember  # noqa: F401
from models.tradie_category import TradieCategory  # noqa: F401
from models.tradie_certification import TradieCertification  # noqa: F401
from models.tradie_change_request import TradieChangeRequest  # noqa: F401
from models.tradie_pass import TradiePass  # noqa: F401
from models.tradie_preference import TradiePreference  # noqa: F401

# ── Tradie profile and related ───────────────────────────────────────────────
from models.tradie_profile import TradieProfile  # noqa: F401
from models.user import User  # noqa: F401
