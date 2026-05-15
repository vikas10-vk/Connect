from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.category import Category, CategoryLevel
from models.tradie_category import TradieCategory
from models.tradie_profile import TradieProfile
from schemas.category_schema import CategoryCreate, CategoryResponse
from services.auth_service import get_current_user
from services.category_resolver import resolve_to_canonical_trade
from models.user import User
import uuid

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])

# ---------------------------------------------------------------------------
# CANONICAL_SLUGS — the 24 official trade categories.
# The category picker shown to tradies ONLY displays these slugs.
# Any other level-1 rows in the DB are orphan synonyms from the old seed
# (e.g. "Plumber", "Electrician") and must not appear in the UI.
# ---------------------------------------------------------------------------
CANONICAL_SLUGS = frozenset([
    "plumbing", "electrical", "carpentry", "painting", "tiling",
    "roofing", "hvac", "landscaping", "concreting", "plastering",
    "flooring", "fencing", "glazing", "pest-control", "security",
    "solar", "gas-fitting", "demolition", "waterproofing", "cleaning",
    "handyman", "building", "bathroom-renovation", "kitchen-renovation",
])


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
    """
    Return ONLY the 24 canonical trade categories for the tradie preferences picker.

    Orphan synonym categories ("Plumber", "Electrician", etc.) created by the
    old seed script are intentionally excluded via the CANONICAL_SLUGS filter.
    This prevents tradies from ever selecting a non-canonical category, which
    would cause their leads to not match homeowner jobs.
    """
    result = await db.execute(
        select(Category)
        .where(
            Category.level == CategoryLevel.TRADE,
            Category.is_active == True,
            Category.slug.in_(CANONICAL_SLUGS),
        )
        .order_by(Category.name)
    )
    return result.scalars().all()


@router.post("/my-categories/{category_id}", status_code=201)
async def add_my_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can select categories")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your tradie profile first")

    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Use resolve_to_canonical_trade (not just canonical_trade_category) so that
    # orphan synonym rows like "Plumber" are normalised to "Plumbing" before saving.
    # Without this, TradieCategory.category_id would store the "Plumber" UUID,
    # which never matches any job's category_id (which is always "Plumbing").
    trade_category = await resolve_to_canonical_trade(db, category)
    if not trade_category:
        raise HTTPException(status_code=400, detail="Please select a valid trade service.")
    category_id = trade_category.id

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
        return []

    result = await db.execute(
        select(TradieCategory).where(TradieCategory.tradie_id == profile.id)
    )
    links = result.scalars().all()

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
