import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.category import Category, CategoryLevel
from models.tradie_category import TradieCategory
from models.tradie_profile import TradieProfile
from models.user import User
from schemas.category_schema import CategoryCreate, CategoryResponse
from services.auth_service import get_current_user
from services.category_resolver import resolve_to_canonical_trade
from services.tradie_change_requests import (
    TradieChangeRequestType,
    create_pending_change_request,
)

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])

# ---------------------------------------------------------------------------
# CANONICAL_SLUGS -- the 24 official trade categories.
# The category picker shown to tradies ONLY displays these slugs at level 1.
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Category creation is an admin-only operation. Previously this endpoint
    # had NO authentication at all — any anonymous caller could inject
    # categories, which corrupts the tradie/job matching taxonomy.
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

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


@router.get("/{trade_id}/subcategories", response_model=list[CategoryResponse])
async def list_subcategories(trade_id: str, db: AsyncSession = Depends(get_db)):
    """
    List the level-2 subcategories under a level-1 trade.

    Used by the tradie preferences page: once a tradie picks "Cleaning" they
    are shown checkboxes for its subcategories ("Pool Cleaning", "End of Lease
    Cleaning", "Carpet Steam Cleaning", etc.) so they can register at the
    specificity that matches what they actually do. This is what stops the
    "pool-only tradie gets office-cleaning leads" mismatch at its source.
    """
    parent_res = await db.execute(select(Category).where(Category.id == trade_id))
    parent = parent_res.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Trade category not found")
    if parent.level != CategoryLevel.TRADE:
        raise HTTPException(status_code=400, detail="Subcategories are only listed under level-1 trades")

    result = await db.execute(
        select(Category)
        .where(
            Category.parent_id == trade_id,
            Category.level == CategoryLevel.SUBCATEGORY,
            Category.is_active == True,
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
    """
    Add a category to the tradie's service profile.

    A tradie can register at either:
      * a Level-1 trade row (e.g. "Cleaning") -- they cover the whole trade, OR
      * a Level-2 subcategory row (e.g. "Pool Cleaning") -- they specialise.

    Specialist registration is preferred because it lets the matcher's
    specificity scoring route exact-fit jobs to specialists ahead of
    generalists. Either is acceptable; the matcher handles both correctly.

    Orphan synonym Level-1 rows ("Plumber", "Electrician", etc.) are still
    normalised to their canonical Level-1 trade via resolve_to_canonical_trade
    -- otherwise the registration is stored at a UUID that no job will match.
    """
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

    # Resolve to the row we will actually save.
    #   Level-2 (subcategory) and Level-3 (task) selections are kept as-is so
    #   that specialist tradies can be matched at their true specificity.
    #   Level-1 selections still pass through resolve_to_canonical_trade so
    #   orphan synonyms ("Plumber") collapse to the canonical row ("Plumbing").
    if category.level == CategoryLevel.TRADE:
        canonical = await resolve_to_canonical_trade(db, category)
        if not canonical:
            raise HTTPException(status_code=400, detail="Please select a valid trade service.")
        save_category = canonical
    else:
        # Subcategory or task -- keep as-is. Walk up the tree to make sure
        # the row actually belongs to a canonical trade (safety check against
        # orphan subcategory rows from old seeds).
        from services.category_resolver import canonical_trade_category
        trade_root = await canonical_trade_category(db, category)
        if not trade_root or trade_root.slug not in CANONICAL_SLUGS:
            raise HTTPException(status_code=400, detail="Please select a valid trade service.")
        save_category = category

    category_id = save_category.id

    result = await db.execute(
        select(TradieCategory).where(
            TradieCategory.tradie_id == profile.id,
            TradieCategory.category_id == category_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category already added")

    if profile.verification_status == "verified":
        await create_pending_change_request(
            db,
            tradie_id=profile.id,
            requested_by=current_user.id,
            request_type=TradieChangeRequestType.SERVICE_ADD,
            payload={
                "category_id": category_id,
                "category_name": save_category.name,
                "category_slug": save_category.slug,
                "category_level": save_category.level,
            },
            note="Verified tradie requested a new service.",
        )
        await db.commit()
        return {
            "message": "Service change sent to admin for approval.",
            "pending_admin_review": True,
        }

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

    if profile.verification_status == "verified":
        cat_res = await db.execute(select(Category).where(Category.id == category_id))
        category = cat_res.scalar_one_or_none()
        await create_pending_change_request(
            db,
            tradie_id=profile.id,
            requested_by=current_user.id,
            request_type=TradieChangeRequestType.SERVICE_REMOVE,
            payload={
                "category_id": category_id,
                "category_name": category.name if category else None,
                "category_slug": category.slug if category else None,
            },
            note="Verified tradie requested service removal.",
        )
        await db.commit()
        return {
            "message": "Service removal sent to admin for approval.",
            "pending_admin_review": True,
        }

    await db.delete(link)
    await db.commit()
    return {"message": "Category removed"}
