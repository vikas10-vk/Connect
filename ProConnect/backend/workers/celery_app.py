"""
workers/celery_app.py

FINAL — adds two new beat schedule entries and task routes:
  auto_close_completed_jobs  Every 30 min — closes completed jobs after 48h dispute window
  detect_no_shows            Every 5 min  — alerts on tradie no-shows, cancels at T+60min
  auto_reject_scope_change   Countdown task (not beat) — registered in task_routes only
"""

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
import os
from models.service_question import ServiceQuestion

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=False,
)

import models

# Broker / result backend.
# Prefer the dedicated CELERY_* variables (separate Redis logical DBs) so the
# task queues do NOT share Redis DB 0 with the app cache, sessions and
# rate-limit keys. Fall back to REDIS_URL only for local/dev convenience.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

celery_app = Celery(
    "ProConnect",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "tasks.lead_tasks",
        "tasks.outbox_tasks",
        "tasks.verification_tasks",
        "tasks.timeout_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Australia/Sydney",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    task_queues={
        "critical": {"exchange": "critical", "routing_key": "critical"},
        "normal":   {"exchange": "normal",   "routing_key": "normal"},
        "bulk":     {"exchange": "bulk",     "routing_key": "bulk"},
    },
    task_default_queue="normal",
    task_default_exchange="normal",
    task_default_routing_key="normal",

    task_routes={
        # ── critical — homeowner / tradie are waiting, never delay ─────────
        "tasks.lead_tasks.distribute_leads":                        {"queue": "critical"},
        "tasks.lead_tasks.auto_reject_scope_change":                {"queue": "critical"},
        # ^ scope change timeout is critical — homeowner is blocked waiting
        "tasks.lead_tasks.redistribute_open_jobs_for_tradie":       {"queue": "critical"},
        # ^ fired on tradie verification — retroactively delivers 0-lead jobs

        # ── normal — time-sensitive operations ─────────────────────────────
        "tasks.verification_tasks.notify_verification_decisions":   {"queue": "normal"},
        "tasks.verification_tasks.notify_review_decisions":         {"queue": "normal"},
        "tasks.verification_tasks.check_cert_expiry":               {"queue": "normal"},
        "tasks.verification_tasks.check_insurance_expiry":          {"queue": "normal"},
        "tasks.verification_tasks.watchdog_ghost_jobs":             {"queue": "normal"},
        "tasks.lead_tasks.auto_close_completed_jobs":               {"queue": "normal"},
        "tasks.lead_tasks.detect_no_shows":                         {"queue": "normal"},
        "tasks.timeout_tasks.check_stale_jobs":                     {"queue": "normal"},
        "tasks.timeout_tasks.redistribute_stale_jobs":              {"queue": "normal"},
        "tasks.outbox_tasks.process_outbox_events":                 {"queue": "normal"},

        # ── bulk — background, delay-tolerant ──────────────────────────────
    },
)

# ── Beat schedule ──────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {

    # ── Verification + review decision emails (every 2 min) ───────────────
    "notify-verification-decisions": {
        "task":     "tasks.verification_tasks.notify_verification_decisions",
        "schedule": 120.0,
        "options":  {"queue": "normal"},
    },
    "notify-review-decisions": {
        "task":     "tasks.verification_tasks.notify_review_decisions",
        "schedule": 120.0,
        "options":  {"queue": "normal"},
    },

    # ── Stale job checks ──────────────────────────────────────────────────
    "check-stale-jobs": {
        "task":     "tasks.timeout_tasks.check_stale_jobs",
        "schedule": crontab(minute=0, hour="*/2"),
        "options":  {"queue": "normal"},
    },
    "redistribute-stale-jobs": {
        "task":     "tasks.timeout_tasks.redistribute_stale_jobs",
        "schedule": crontab(minute=30, hour="*/6"),
        "options":  {"queue": "normal"},
    },

    # ── Licence expiry monitoring (daily at 6am) ──────────────────────────
    "check-cert-expiry": {
        "task":     "tasks.verification_tasks.check_cert_expiry",
        "schedule": crontab(hour=6, minute=0),
        "options":  {"queue": "normal"},
    },

    # ── Insurance expiry monitoring (daily at 6:15am) ─────────────────────
    "check-insurance-expiry": {
        "task":     "tasks.verification_tasks.check_insurance_expiry",
        "schedule": crontab(hour=6, minute=15),
        "options":  {"queue": "normal"},
    },

    # ── Ghost job watchdog (every 5 min) ──────────────────────────────────
    "watchdog-ghost-jobs": {
        "task":     "tasks.verification_tasks.watchdog_ghost_jobs",
        "schedule": 300.0,
        "options":  {"queue": "normal"},
    },

    # ── Auto-close completed jobs after 48h dispute window (every 30 min) ─
    # Finds jobs in 'completed' > 48h old with no dispute → transitions to 'closed'.
    # This unblocks payment release and enables review submission.
    "auto-close-completed-jobs": {
        "task":     "tasks.lead_tasks.auto_close_completed_jobs",
        "schedule": 1800.0,
        "options":  {"queue": "normal"},
    },

    # ── No-show detection (every 5 min) ───────────────────────────────────
    # T+30min alert to homeowner + warning to tradie.
    # T+60min auto-cancel + full refund + tradie flag.
    "detect-no-shows": {
        "task":     "tasks.lead_tasks.detect_no_shows",
        "schedule": 300.0,
        "options":  {"queue": "normal"},
    },
    "process-outbox-events": {
        "task":     "tasks.outbox_tasks.process_outbox_events",
        "schedule": 60.0,
        "options":  {"queue": "normal"},
    },
}
