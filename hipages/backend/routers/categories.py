from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.category import Category
from models.tradie_category import TradieCategory
from models.tradie_profile import TradieProfile
from schemas.category_schema import CategoryCreate, CategoryResponse
from services.auth_service import get_current_user
from models.user import User
import uuid

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])

@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Category).where(Category.slug == body.slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category slug already exists")

    category = Category(id=str(uuid.uuid4()), **body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

@router.get("", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()

@router.post("/my-categories/{category_id}", status_code=201)
async def add_my_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can select categories")

    # Get tradie profile
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your tradie profile first")

    # Check category exists
    result = await db.execute(select(Category).where(Category.id == category_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Category not found")

    # Check not already added
    result = await db.execute(
        select(TradieCategory).where(
            TradieCategory.tradie_id == profile.id,
            TradieCategory.category_id == category_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category already added")

    link = TradieCategory(tradie_id=profile.id, category_id=category_id)
    db.add(link)
    await db.commit()
    return {"message": "Category added"}


@router.get("/my-categories")
async def get_my_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the list of categories this tradie has selected."""
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can view categories")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return []   # No profile yet — return empty list, not 404

    result = await db.execute(
        select(TradieCategory).where(TradieCategory.tradie_id == profile.id)
    )
    links = result.scalars().all()

    # Return with category_id so frontend can match
    return [{"category_id": lnk.category_id, "tradie_id": lnk.tradie_id} for lnk in links]


@router.delete("/my-categories/{category_id}", status_code=200)
async def remove_my_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a category from this tradie's profile."""
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can modify categories")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your tradie profile first")

    result = await db.execute(
        select(TradieCategory).where(
            TradieCategory.tradie_id == profile.id,
            TradieCategory.category_id == category_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Category not found on your profile")

    await db.delete(link)
    await db.commit()
    return {"message": "Category removed"}