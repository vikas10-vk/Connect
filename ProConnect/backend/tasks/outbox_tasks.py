from datetime import datetime

from celery import shared_task
from sqlalchemy import select

from models.outbox_event import OutboxEvent


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="normal")
def process_outbox_events(self, limit: int = 50):
    from tasks.lead_tasks import _run_task

    _run_task(lambda sf: _process_outbox_events(sf, limit))


async def _process_outbox_events(session_factory, limit: int) -> None:
    from tasks.lead_tasks import distribute_leads

    async with session_factory() as db:
        result = await db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        events = result.scalars().all()

        for event in events:
            try:
                if event.event_type == "job.created":
                    job_id = event.payload["job_id"]
                    task = distribute_leads.apply_async(args=[job_id], queue="critical")
                    event.status = "queued"
                    event.processed_at = datetime.utcnow()
                    event.payload = {**event.payload, "lead_task_id": task.id}
                else:
                    event.status = "ignored"
                    event.processed_at = datetime.utcnow()
                    event.last_error = f"Unknown event_type: {event.event_type}"
            except Exception as exc:
                event.attempts = (event.attempts or 0) + 1
                event.last_error = str(exc)[:2000]
                if event.attempts >= 5:
                    event.status = "failed"
                    event.processed_at = datetime.utcnow()
            db.add(event)

        await db.commit()
