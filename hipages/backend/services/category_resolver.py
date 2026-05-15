"""
Resolve homeowner service text and tradie selections to the same trade row.

Jobs and tradie preferences are matched by ``TradieCategory.category_id``.
That id must always be the canonical level-1 trade category, even when the
input was a service alias ("plumber") or a taxonomy child ("Blocked Drains").
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.category import Category, CategoryLevel


# ---------------------------------------------------------------------------
# SYNONYM → CANONICAL SLUG MAP
# ---------------------------------------------------------------------------
# The old seed script (scripts/seed_categories.py) created 148+ agent-noun
# categories ("Plumber", "Electrician", etc.) as separate level-1 DB rows
# alongside the canonical 24 ("Plumbing", "Electrical", etc.).
#
# A tradie who selected "Plumber" has TradieCategory.category_id pointing at
# the "Plumber" row.  A job resolved via TRADE_ALIASES lands on "Plumbing".
# These are different UUIDs → no match → lead never sent.
#
# This map is the single source of truth for collapsing all synonym/orphan
# categories to the correct canonical slug.  Keys are lowercase normalised.
# ---------------------------------------------------------------------------
SYNONYM_TO_CANONICAL_SLUG: dict[str, str] = {
    # Plumbing
    "plumber": "plumbing",
    "gas fitter": "gas-fitting",
    "gas fitting": "gas-fitting",
    "rainwater tanks installer": "plumbing",
    "rainwater tanks installer / supplier": "plumbing",
    # Electrical
    "electrician": "electrical",
    "antenna installer": "electrical",
    "antenna installer / supplier": "electrical",
    # Carpentry / Joinery
    "carpenter": "carpentry",
    "joiner": "carpentry",
    "cabinet maker": "carpentry",
    "deck builder": "carpentry",
    "garage door installer": "carpentry",
    "garage door installer / supplier": "carpentry",
    "patio builder": "carpentry",
    "pergola builder": "carpentry",
    "shade and sail installer": "carpentry",
    "shade and sail installer / supplier": "carpentry",
    "shed builder": "carpentry",
    "shed builder / supplier": "carpentry",
    "staircase builder": "carpentry",
    # Painting
    "painter": "painting",
    # Tiling
    "tiler": "tiling",
    # Roofing
    "roofer": "roofing",
    "gutter cleaner": "roofing",
    "gutter guard installer": "roofing",
    # HVAC
    "air conditioning installer": "hvac",
    "air conditioning installer / supplier": "hvac",
    "heating specialist": "hvac",
    # Landscaping
    "landscaper": "landscaping",
    "gardener": "landscaping",
    "arborist": "landscaping",
    "lawn mowing services": "landscaping",
    "retaining wall builder": "landscaping",
    "tree lopper": "landscaping",
    "tree surgeon": "landscaping",
    # Concreting
    "concretor": "concreting",
    "concreter": "concreting",
    "paving": "concreting",
    "paving supplier": "concreting",
    "driveway installer": "concreting",
    # Plastering
    "plasterer": "plastering",
    "renderer": "plastering",
    "bath and basin resurfacing": "plastering",
    # Flooring
    "floor layer": "flooring",
    "carpet layer": "flooring",
    "carpet layer / repairs": "flooring",
    "floor polisher": "flooring",
    "floor sander": "flooring",
    "bamboo flooring installer": "flooring",
    "bamboo flooring installer / supplier": "flooring",
    # Fencing
    "fencer": "fencing",
    "fence installer": "fencing",
    "balustrading installer": "fencing",
    "pool fence installer": "fencing",
    "pool fence installer / maintenance": "fencing",
    # Glazing
    "glazier": "glazing",
    "shower screen installer": "glazing",
    "shower screen installer / supplier": "glazing",
    "screen enclosure supplier": "glazing",
    "window installer": "glazing",
    "window tinter": "glazing",
    # Pest Control
    "pest controller": "pest-control",
    "pest control services": "pest-control",
    "pest inspector": "pest-control",
    # Security
    "security systems specialist": "security",
    "locksmith": "security",
    # Solar
    "solar installer": "solar",
    "solar hot water system installer": "solar",
    # Demolition
    "demolisher": "demolition",
    "excavator": "demolition",
    "excavator / earthmoving": "demolition",
    # Waterproofing
    "waterproofer": "waterproofing",
    # Cleaning
    "cleaner": "cleaning",
    "commercial cleaning services": "cleaning",
    "pressure cleaning services": "cleaning",
    "carpet / upholstery cleaning": "cleaning",
    "mattress cleaning": "cleaning",
    "pool maintenance services": "cleaning",
    "rubbish removal services": "cleaning",
    "skip bin hire": "cleaning",
    # Handyman
    "handyman": "handyman",
    "appliance installer": "handyman",
    "appliance repairer": "handyman",
    # Building & Construction
    "builder": "building",
    "bricklayer": "building",
    "building certifier": "building",
    "building consultant": "building",
    "building designer": "building",
    "building inspector": "building",
    "building surveyor": "building",
    "carport builder": "building",
    "cladding installer": "building",
    "insulation installer": "building",
    "pool builder": "building",
    "renovation and extensions builder": "building",
    "scaffolding services": "building",
    "stonemason": "building",
    "swimming pool builder": "building",
    "tuckpointer": "building",
    # Bathroom / Kitchen Renovation
    "bathroom building / renovations": "bathroom-renovation",
    "bathroom renovator": "bathroom-renovation",
    "kitchen renovator": "kitchen-renovation",
    "kitchen cabinet maker": "kitchen-renovation",
}

TRADE_ALIASES: dict[str, tuple[str, ...]] = {
    "plumbing": (
        "plumb", "plumber", "tap", "drain", "toilet", "pipe", "leak",
        "hot water", "water heater", "cistern", "sewage", "blocked drain",
        "stormwater", "drainage", "pipe relining", "low water pressure",
    ),
    "electrical": (
        "electric", "electrician", "power point", "powerpoint", "light",
        "switch", "switchboard", "circuit", "wiring", "downlight", "ceiling fan",
        "ev charger", "data point", "nbn", "smoke alarm", "fault finding",
    ),
    "painting": (
        "paint", "painter", "painting", "decorating", "wallpaper",
        "interior painting", "exterior painting", "roof painting", "render painting",
    ),
    "carpentry": (
        "carpenter", "carpentry", "joinery", "timber", "wood", "deck",
        "door", "pergola", "wardrobe", "cabinet", "stair", "balustrade",
        "cladding", "framing", "built in", "shelving",
    ),
    "tiling": ("tile", "tiling", "grout", "regrout", "splashback"),
    "roofing": (
        "roof", "roofer", "gutter", "downpipe", "fascia", "flashing",
        "ridge capping", "skylight", "roof insulation", "colorbond roof",
    ),
    "hvac": (
        "air con", "aircon", "air conditioning", "hvac", "split system",
        "ducted", "heating", "cooling", "evaporative", "heat pump",
    ),
    "landscaping": (
        "garden", "gardening", "landscape", "lawn", "mow", "tree",
        "hedge", "turf", "irrigation", "retaining wall", "stump grinding",
        "paving garden", "yard clean",
    ),
    "concreting": (
        "concrete", "concreting", "driveway", "path", "footpath", "slab",
        "paver", "paving", "resurfacing",
    ),
    "plastering": (
        "plaster", "plastering", "plasterboard", "gyprock", "cornice",
        "moulding", "render", "patch wall", "hole in wall",
    ),
    "flooring": (
        "floor", "flooring", "timber floor", "hybrid floor", "laminate",
        "carpet", "vinyl", "floor sanding", "floor polish",
    ),
    "fencing": ("fence", "fencing", "gate", "colorbond", "pool fence", "driveway gate"),
    "glazing": (
        "glazing", "glass", "window glass", "broken window", "shower screen",
        "glass splashback", "mirror", "double glazing",
    ),
    "pest-control": (
        "pest", "termite", "rodent", "cockroach", "ant", "spider", "possum",
        "wasp", "pest control",
    ),
    "security": (
        "security", "alarm", "cctv", "camera", "intercom", "deadbolt",
        "smart lock", "access control",
    ),
    "solar": (
        "solar", "solar panel", "battery storage", "home battery",
        "photovoltaic", "pv system", "solar hot water",
    ),
    "gas-fitting": (
        "gas fitting", "gas fitter", "gas leak", "gas appliance", "gas cooktop",
        "gas oven", "gas heater", "gas line", "gas hot water", "gas bbq",
    ),
    "demolition": ("demolition", "demolish", "knockdown", "site clearance", "strip out"),
    "waterproofing": (
        "waterproof", "waterproofing", "wet area", "deck waterproof",
        "balcony waterproof", "below slab waterproof",
    ),
    "cleaning": (
        "clean", "cleaning", "bond clean", "end of lease", "deep clean",
        "builders clean", "pressure wash", "window clean", "carpet steam",
    ),
    "handyman": (
        "handyman", "flat pack", "flatpack", "odd job", "minor repair",
        "tv mount", "furniture assembly", "general repairs",
    ),
    "building": (
        "builder", "building", "construction", "extension", "addition",
        "renovation", "granny flat", "structural", "shed", "garage",
    ),
    "bathroom-renovation": (
        "bathroom renovation", "bathroom reno", "ensuite renovation",
        "full bathroom", "bathroom strip out", "vanity replacement",
        "shower replacement", "bath replacement",
    ),
    "kitchen-renovation": (
        "kitchen renovation", "kitchen reno", "kitchen cabinet",
        "cabinet replacement", "benchtop", "kitchen splashback",
        "kitchen install",
    ),
}


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains_phrase(haystack: str, phrase: str) -> bool:
    normalised = _normalise(phrase)
    return bool(re.search(rf"\b{re.escape(normalised)}\b", haystack))


def _phrase_score(phrase: str) -> int:
    words = _normalise(phrase).split()
    # Specific multi-word service phrases beat broad trade words.
    return 10 + len(words) * 6 + len("".join(words)) // 4


async def canonical_trade_category(db: AsyncSession, category: Category) -> Category | None:
    """Return the level-1 parent for any taxonomy row."""
    current = category
    seen: set[str] = set()

    while current and current.level != CategoryLevel.TRADE:
        if not current.parent_id or current.id in seen:
            return None
        seen.add(current.id)
        parent_res = await db.execute(select(Category).where(Category.id == current.parent_id))
        current = parent_res.scalar_one_or_none()

    return current if current and current.level == CategoryLevel.TRADE else None


async def resolve_trade_category(db: AsyncSession, service_text: str) -> Category | None:
    """
    Resolve user/tradie service input to a canonical level-1 trade category.

    The resolver is deliberately strict: exact slug/name first, then explicit
    aliases. It avoids loose SQL ``contains`` matching because that can silently
    turn one service into another.
    """
    text = _normalise(service_text or "")
    if not text:
        return None

    slug_text = text.replace(" ", "-")
    exact_res = await db.execute(
        select(Category).where(
            Category.is_active == True,
            func.lower(Category.slug) == slug_text,
        )
    )
    exact = exact_res.scalar_one_or_none()
    if not exact:
        exact_res = await db.execute(
            select(Category).where(
                Category.is_active == True,
                func.lower(Category.name) == text,
            )
        )
        exact = exact_res.scalar_one_or_none()

    if exact:
        return await canonical_trade_category(db, exact)

    scores: dict[str, int] = {}

    category_res = await db.execute(select(Category).where(Category.is_active == True))
    for category in category_res.scalars().all():
        phrases = {
            category.name,
            category.slug.replace("-", " "),
        }
        for phrase in phrases:
            if _contains_phrase(text, phrase):
                trade = await canonical_trade_category(db, category)
                if not trade:
                    continue
                level_bonus = 18 if category.level == CategoryLevel.TASK else 10 if category.level == CategoryLevel.SUBCATEGORY else 0
                scores[trade.slug] = max(scores.get(trade.slug, 0), _phrase_score(phrase) + level_bonus)

    for trade_slug, aliases in TRADE_ALIASES.items():
        for alias in aliases:
            if _contains_phrase(text, alias):
                scores[trade_slug] = max(scores.get(trade_slug, 0), _phrase_score(alias))

    if not scores:
        return None

    best_slug, best_score = max(scores.items(), key=lambda item: item[1])
    tied = [slug for slug, score in scores.items() if score == best_score]
    if len(tied) > 1:
        return None

    trade_res = await db.execute(
        select(Category).where(
            Category.slug == best_slug,
            Category.level == CategoryLevel.TRADE,
            Category.is_active == True,
        )
    )
    trade = trade_res.scalar_one_or_none()
    if trade:
        return trade

    return None


async def resolve_to_canonical_trade(db: AsyncSession, category: Category) -> Category | None:
    """
    Resolve any Category row — including orphan synonym rows created by the old
    seed script (e.g. "Plumber", "Electrician") — to the correct canonical
    level-1 trade category.

    Resolution order:
      1. Walk parent_id tree (standard taxonomy traversal via canonical_trade_category).
      2. If the result IS already level-1 but its normalised name appears in
         SYNONYM_TO_CANONICAL_SLUG, fetch and return the canonical row instead.
         This is the fix for: tradie picks "Plumber" (orphan L1) → stored as
         "Plumbing" (canonical L1).
      3. Otherwise return whatever canonical_trade_category returned.

    Use this function everywhere a category row is being saved to TradieCategory,
    instead of calling canonical_trade_category directly.
    """
    trade = await canonical_trade_category(db, category)
    if not trade:
        return None

    # Check if this level-1 result is actually a synonym orphan
    key = _normalise(trade.name)
    canonical_slug = SYNONYM_TO_CANONICAL_SLUG.get(key)
    if not canonical_slug:
        # Also try slug-based lookup (e.g. slug="plumber" → canonical slug "plumbing")
        slug_key = _normalise(trade.slug.replace("-", " "))
        canonical_slug = SYNONYM_TO_CANONICAL_SLUG.get(slug_key)

    if canonical_slug:
        canonical_res = await db.execute(
            select(Category).where(
                Category.slug == canonical_slug,
                Category.level == CategoryLevel.TRADE,
                Category.is_active == True,
            )
        )
        canonical = canonical_res.scalar_one_or_none()
        if canonical:
            return canonical

    return trade
