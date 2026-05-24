import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.home_asset import HomeAsset
from models.user import User
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])

ASSET_LIFESPANS = {
    "Hot Water System":  120,
    "Air Conditioner":   180,
    "Electrical Board":  240,
    "Roof":              360,
    "Fence":             180,
    "Plumbing":          240,
    "Solar Panels":      300,
    "Gas System":        180,
    "Pool & Spa":        120,
    "Heating System":    180,
    "Security System":   120,
    "Garage Door":       120,
    "Pest Control":       12,
    "Painting":           60,
    "Flooring":          180,
}

class AssetCreate(BaseModel):
    asset_type:        str
    brand_name:        str
    installation_date: date
    warranty_months:   int = 12
    tradie_name:       str | None = None
    job_id:            str | None = None
    invoice_number:    str | None = None
    notes:             str | None = None

class AssetUpdate(BaseModel):
    brand_name:        str | None  = None
    installation_date: date | None = None
    warranty_months:   int | None  = None
    tradie_name:       str | None  = None
    job_id:            str | None  = None
    invoice_number:    str | None  = None
    notes:             str | None  = None


@router.post("/")
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can add assets")

    lifespan = ASSET_LIFESPANS.get(body.asset_type, 120)

    asset = HomeAsset(
        id                = str(uuid.uuid4()),
        homeowner_id      = current_user.id,
        asset_type        = body.asset_type,
        brand_name        = body.brand_name,
        installation_date = body.installation_date,
        warranty_months   = body.warranty_months,
        tradie_name       = body.tradie_name,
        job_id            = body.job_id,
        invoice_number    = body.invoice_number,
        notes             = body.notes,
        expected_lifespan = lifespan,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)


@router.get("/mine")
async def get_my_assets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(HomeAsset)
        .where(HomeAsset.homeowner_id == current_user.id)
        .order_by(HomeAsset.created_at.desc())
    )
    assets = result.scalars().all()
    return [_serialize(a) for a in assets]


@router.put("/{asset_id}")
async def update_asset(
    asset_id: str,
    body: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(HomeAsset).where(
            HomeAsset.id == asset_id,
            HomeAsset.homeowner_id == current_user.id
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    for field, value in body.dict(exclude_none=True).items():
        setattr(asset, field, value)

    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(HomeAsset).where(
            HomeAsset.id == asset_id,
            HomeAsset.homeowner_id == current_user.id
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    await db.delete(asset)
    await db.commit()
    return {"deleted": True}


def _serialize(asset: HomeAsset) -> dict:
    return {
        "id":                asset.id,
        "asset_type":        asset.asset_type,
        "brand_name":        asset.brand_name,
        "installation_date": str(asset.installation_date),
        "warranty_months":   asset.warranty_months,
        "tradie_name":       asset.tradie_name,
        "job_id":            asset.job_id,
        "invoice_number":    asset.invoice_number,
        "notes":             asset.notes,
        "expected_lifespan": asset.expected_lifespan,
        "created_at":        asset.created_at.isoformat(),
    }
