"""
Suburb search and postcode lookup endpoints.

GET /suburbs/search?q=mel&limit=8            — autocomplete (booking page)
GET /suburbs/postcode/{postcode}              — all suburbs for a postcode
GET /suburbs/state/{state_code}              — all suburbs in a state (for filtering)
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional

from db.session import get_db
from models.suburb import Suburb

router = APIRouter(prefix="/suburbs", tags=["suburbs"])


# ---------------------------------------------------------------------------
# GET /suburbs/search?q=melb&limit=8
# Used by: booking page autocomplete, tradie profile suburb picker
# ---------------------------------------------------------------------------
@router.get("/search")
async def search_suburbs(
    q:     str           = Query(..., min_length=2, description="Suburb name prefix"),
    limit: int           = Query(8,  ge=1, le=20),
    state: Optional[str] = Query(None, description="Filter by state_code e.g. VIC"),
    db:    AsyncSession  = Depends(get_db),
):
    """
    Fast prefix + contains search on suburb name and postcode.
    Returns label formatted as 'Suburb, STATE postcode' for autocomplete.
    """
    term = q.strip().lower()

    query = select(Suburb).filter(
        or_(
            func.lower(Suburb.suburb).contains(term),
            Suburb.postcode.contains(term)
        )
    )

    if state:
        query = query.filter(Suburb.state_code == state.upper())

    # Prioritise exact matches or prefix matches
    query = query.order_by(
        # Postcode exact match or prefix match first, then suburb prefix match
        Suburb.postcode.like(f"{term}%").desc(),
        func.lower(Suburb.suburb).like(f"{term}%").desc(),
        Suburb.suburb,
    ).limit(limit)

    result = await db.execute(query)
    results = result.scalars().all()

    return [r.to_dict() for r in results]


# ---------------------------------------------------------------------------
# GET /suburbs/postcode/3000
# Used by: lead distribution — find suburb name for a raw postcode
# ---------------------------------------------------------------------------
@router.get("/postcode/{postcode}")
async def get_by_postcode(
    postcode: str,
    db:       AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Suburb).filter(Suburb.postcode == postcode.strip()))
    results = result.scalars().all()
    if not results:
        raise HTTPException(status_code=404, detail=f"No suburbs found for postcode {postcode}")
    return [r.to_dict() for r in results]


# ---------------------------------------------------------------------------
# GET /suburbs/state/VIC
# Used by: admin / filtering tradies by state
# ---------------------------------------------------------------------------
@router.get("/state/{state_code}")
async def get_by_state(
    state_code: str,
    db:         AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Suburb)
        .filter(Suburb.state_code == state_code.upper())
        .order_by(Suburb.suburb)
    )
    results = result.scalars().all()
    if not results:
        raise HTTPException(status_code=404, detail=f"No suburbs found for state {state_code}")
    return [r.to_dict() for r in results]