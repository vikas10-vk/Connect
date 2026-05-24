import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tradie_change_request import (
    TradieChangeRequest,
    TradieChangeRequestStatus,
    TradieChangeRequestType,
)


def _stable_payload(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


async def create_pending_change_request(
    db: AsyncSession,
    *,
    tradie_id: str,
    requested_by: str,
    request_type: str,
    payload: dict[str, Any],
    note: str | None = None,
) -> TradieChangeRequest:
    payload_text = _stable_payload(payload)
    existing_res = await db.execute(
        select(TradieChangeRequest).where(
            TradieChangeRequest.tradie_id == tradie_id,
            TradieChangeRequest.request_type == request_type,
            TradieChangeRequest.status == TradieChangeRequestStatus.PENDING,
            TradieChangeRequest.payload == payload_text,
        )
    )
    existing = existing_res.scalar_one_or_none()
    if existing:
        return existing

    req = TradieChangeRequest(
        id=str(uuid.uuid4()),
        tradie_id=tradie_id,
        requested_by=requested_by,
        request_type=request_type,
        status=TradieChangeRequestStatus.PENDING,
        payload=payload_text,
        note=note,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    return req


def parse_change_payload(req: TradieChangeRequest) -> dict[str, Any]:
    try:
        return json.loads(req.payload)
    except Exception:
        return {}


__all__ = [
    "TradieChangeRequest",
    "TradieChangeRequestStatus",
    "TradieChangeRequestType",
    "create_pending_change_request",
    "parse_change_payload",
]
