import os
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=r"C:\Users\Capstone\Intership_main\hipages\.env",
    override=True
)

# ── Sentry — must be initialised before anything else ─────────────
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.celery import CeleryIntegration


SENTRY_DSN = os.getenv("SENTRY_BACKEND_DSN")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=1.0,       # 100% of transactions in dev; lower to 0.1 in prod
        profiles_sample_rate=0.1,     # 10% profiling sample
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),   # captures slow/failed DB queries
            CeleryIntegration(),       # captures Celery task errors
        ],
        # Strip sensitive data from error reports
        send_default_pii=False,
    )
    print(f"[OK] Sentry initialised — environment: {os.getenv('ENVIRONMENT', 'development')}")
else:
    print("[WARNING] SENTRY_BACKEND_DSN not set — Sentry disabled")
# ──────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db.session import get_db

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
from models.audit_event import AuditEvent
from models.job_event import JobEvent
from models.suburb import Suburb
from models.email_otp import EmailOTP

from routers.auth import router as auth_router
from routers.tradies import router as tradies_router
from routers.categories import router as categories_router
from routers.jobs import router as jobs_router
from routers.leads import router as leads_router
from routers.quotes import router as quotes_router
from routers.reviews import router as reviews_router
from routers.websocket import router as ws_router
from routers.payments import router as payments_router
from routers.uploads import router as uploads_router
from models.home_asset import HomeAsset
from routers.assets import router as assets_router
from models.tradie_pass       import TradiePass
from models.tradie_preference import TradiePreference
from models.earnings_record   import EarningsRecord
from models.swms_document     import SWMSDocument
from routers.compliance    import router as compliance_router
from routers.licence_guard import router as licence_guard_router
from routers.swms          import router as swms_router
from routers.earnings      import router as earnings_router
from routers.preferences   import router as preferences_router
from models.chat_conversation import ChatConversation
from routers.ai_chat import router as ai_chat_router
from routers.suburbs import router as suburbs_router
from routers.job_assignments import router as job_assignments_router
from middleware.audit_middleware import AuditMiddleware

app = FastAPI(title="ProConnect API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Audit middleware — auto-logs every mutating request ────────────

app.add_middleware(AuditMiddleware)
app.include_router(auth_router)
app.include_router(tradies_router)
app.include_router(categories_router)
app.include_router(jobs_router)
app.include_router(leads_router)
app.include_router(quotes_router)
app.include_router(reviews_router)
app.include_router(ws_router)
app.include_router(payments_router)
app.include_router(uploads_router)
app.include_router(assets_router)
app.include_router(compliance_router)
app.include_router(licence_guard_router)
app.include_router(swms_router)
app.include_router(earnings_router)
app.include_router(preferences_router)
app.include_router(ai_chat_router)
app.include_router(suburbs_router)
app.include_router(job_assignments_router)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        # Sentry captures this automatically
        return {"status": "error", "database": str(e)}


# ── Sentry debug endpoint — REMOVE IN PRODUCTION ──────────────────
@app.get("/sentry-debug")
async def sentry_debug():
    """
    Hit this endpoint once to verify Sentry is receiving errors.
    Remove this route before deploying to production.
    """
    raise ValueError("Sentry test error — if you see this in Sentry, it's working!")