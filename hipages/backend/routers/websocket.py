from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
import os
import json
import asyncio
import logging

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# In-memory connection registry, keyed by user_id (the JWT 'sub').
# A single user may have multiple devices/tabs open at once -- store a SET
# of websockets per user so we broadcast to all of them.
active_connections: dict[str, set[WebSocket]] = {}


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


async def broadcast_job_status(
    job_id:     str,
    old_status: str,
    new_status: str,
    homeowner_id: str | None,
    tradie_user_ids: list[str] | None = None,
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
            await manager.send_to_user(user_id, payload)
        except Exception as exc:
            logger.debug("Status broadcast skipped for user %s: %s", user_id, exc)


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