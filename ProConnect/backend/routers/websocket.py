import asyncio
import json
import logging
import os
from datetime import datetime

import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=False
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])
REALTIME_CHANNEL = os.getenv("REALTIME_REDIS_CHANNEL", "realtime:events")

# In-memory connection registry, keyed by user_id (the JWT 'sub').
# A single user may have multiple devices/tabs open at once -- store a SET
# of websockets per user so we broadcast to all of them.
active_connections: dict[str, set[WebSocket]] = {}
_publisher: aioredis.Redis | None = None
_subscriber_task: asyncio.Task | None = None


class ConnectionManager:
    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        active_connections.setdefault(user_id, set()).add(websocket)
        logger.info("WebSocket connected: user=%s, sockets=%d",
                    user_id, len(active_connections[user_id]))

    def disconnect(self, user_id: str, websocket: WebSocket | None = None):
        sockets = active_connections.get(user_id)
        if not sockets:
            return
        if websocket is None:
            active_connections.pop(user_id, None)
        else:
            sockets.discard(websocket)
            if not sockets:
                active_connections.pop(user_id, None)
        logger.info("WebSocket disconnected: user=%s", user_id)

    async def send_to_user(self, user_id: str, message: dict) -> int:
        """
        Push a message to every live websocket for this user. Returns the
        number of sockets the message reached. Failed sockets are evicted
        from the registry but never raise -- callers can fire-and-forget.
        """
        sockets = list(active_connections.get(user_id, set()))
        if not sockets:
            return 0
        text = json.dumps(message)
        delivered = 0
        for ws in sockets:
            try:
                await ws.send_text(text)
                delivered += 1
            except Exception as exc:
                logger.debug("WS send failed for user %s: %s", user_id, exc)
                self.disconnect(user_id, ws)
        return delivered

    # Backward-compat alias for the original API. Older callers (e.g. the
    # inquiry notification path) use this name. New code should call
    # send_to_user; both routes are equivalent.
    async def send_to_tradie(self, user_id: str, message: dict) -> int:
        return await self.send_to_user(user_id, message)


manager = ConnectionManager()


async def _get_publisher() -> aioredis.Redis:
    global _publisher
    if _publisher is None:
        _publisher = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.5,
            retry_on_timeout=False,
        )
    return _publisher


async def _mark_notification_delivered(notification_id: str | None) -> None:
    if not notification_id:
        return
    try:
        from db.session import AsyncSessionLocal
        from models.realtime_notification import RealtimeNotification

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(RealtimeNotification)
                .where(
                    RealtimeNotification.id == notification_id,
                    RealtimeNotification.delivered_at.is_(None),
                )
                .values(delivered_at=datetime.utcnow())
            )
            await db.commit()
    except Exception:
        logger.debug("Could not mark realtime notification delivered", exc_info=True)


async def _deliver_pubsub_payload(raw: str) -> None:
    try:
        envelope = json.loads(raw)
        user_id = envelope["user_id"]
        payload = envelope["payload"]
    except Exception:
        logger.debug("Invalid realtime pubsub message skipped: %r", raw)
        return

    delivered = await manager.send_to_user(user_id, payload)
    if delivered:
        await _mark_notification_delivered(envelope.get("notification_id"))


async def start_realtime_pubsub(redis_client: aioredis.Redis) -> None:
    """
    Fan Redis pub/sub messages into this process' local WebSocket registry.
    Each API instance runs this listener, so a publish from any instance reaches
    users connected to any other instance.
    """
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        return

    async def _listen() -> None:
        # Create a dedicated redis client to avoid connection pool conflicts
        sub_client = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,
        )
        pubsub = sub_client.pubsub()
        try:
            await pubsub.subscribe(REALTIME_CHANNEL)
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                await _deliver_pubsub_payload(message.get("data"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Realtime pub/sub listener stopped unexpectedly")
        finally:
            try:
                await pubsub.unsubscribe(REALTIME_CHANNEL)
                await pubsub.close()
            except Exception:
                pass
            try:
                await sub_client.aclose()
            except Exception:
                pass

    _subscriber_task = asyncio.create_task(_listen())


async def stop_realtime_pubsub() -> None:
    global _subscriber_task, _publisher
    if _subscriber_task:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None
    if _publisher:
        try:
            await _publisher.aclose()
        except Exception:
            pass
        _publisher = None


async def _send_pending_notifications(user_id: str, websocket: WebSocket) -> None:
    try:
        from db.session import AsyncSessionLocal
        from models.realtime_notification import RealtimeNotification

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RealtimeNotification)
                .where(
                    RealtimeNotification.user_id == user_id,
                    RealtimeNotification.delivered_at.is_(None),
                )
                .order_by(RealtimeNotification.created_at.asc())
                .limit(50)
            )
            rows = result.scalars().all()
            delivered_ids: list[str] = []
            for row in rows:
                payload = dict(row.payload)
                payload.setdefault("notification_id", row.id)
                await websocket.send_text(json.dumps(payload))
                delivered_ids.append(row.id)
            if delivered_ids:
                await db.execute(
                    update(RealtimeNotification)
                    .where(RealtimeNotification.id.in_(delivered_ids))
                    .values(delivered_at=datetime.utcnow())
                )
                await db.commit()
    except Exception:
        logger.debug("Pending realtime notifications skipped for user %s", user_id, exc_info=True)


async def broadcast_job_status(
    job_id:     str,
    old_status: str,
    new_status: str,
    homeowner_id: str | None,
    tradie_user_ids: list[str] | None = None,
    notification_ids: dict[str, str] | None = None,
) -> None:
    """
    Push a job:status_changed event to every party who needs to see it.

    Used by JobStateMachine._execute so the homeowner dashboard and the tradie
    dashboard auto-refresh on any status transition (tradie marks complete,
    homeowner confirms, dispute raised, etc.) without needing manual reload.

    Best-effort by design -- a WebSocket failure can NEVER fail a transition.
    """
    payload = {
        "type":       "job:status_changed",
        "job_id":     job_id,
        "old_status": old_status,
        "new_status": new_status,
    }
    recipients: list[str] = []
    if homeowner_id:
        recipients.append(homeowner_id)
    if tradie_user_ids:
        recipients.extend(t for t in tradie_user_ids if t)

    for user_id in set(recipients):
        try:
            user_payload = dict(payload)
            notification_id = (notification_ids or {}).get(user_id)
            if notification_id:
                user_payload["notification_id"] = notification_id
            message = {
                "user_id": user_id,
                "payload": user_payload,
                "notification_id": notification_id,
            }
            publisher = await _get_publisher()
            await publisher.publish(REALTIME_CHANNEL, json.dumps(message))
        except Exception as exc:
            logger.debug("Redis realtime publish failed for user %s: %s", user_id, exc)
            try:
                await manager.send_to_user(user_id, payload)
            except Exception:
                logger.debug("Local realtime fallback skipped for user %s", user_id, exc_info=True)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: str | None = Query(default=None),
):
    # Authenticate with a short-lived, single-use ticket minted by
    # POST /api/v1/auth/ws-ticket — NOT a long-lived JWT in the URL.
    # The ticket is consumed (atomically read-and-deleted) on first use.
    if not ticket:
        await websocket.close(code=4001)
        return

    try:
        redis_client = websocket.app.state.redis_client
        user_id = await redis_client.getdel(f"ws:ticket:{ticket}")
    except Exception as exc:
        logger.warning("WebSocket ticket lookup failed: %s", exc)
        await websocket.close(code=4001)
        return

    if not user_id:
        await websocket.close(code=4001)
        return
    if isinstance(user_id, bytes):
        user_id = user_id.decode()

    await manager.connect(user_id, websocket)
    await _send_pending_notifications(user_id, websocket)

    try:
        # Keep connection alive -- heartbeat every 30 seconds.
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as exc:
        logger.debug("WebSocket loop ended for user %s: %s", user_id, exc)
        manager.disconnect(user_id, websocket)
