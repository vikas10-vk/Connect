"""
Geocoding service — two providers:

  1. Mapbox    → used for tradie profile setup (accurate, paid, you have the key)
  2. Nominatim → used for job wizard (free, no key needed, already working)

Both return (lat, lng) tuple. Never raise — geocoding failure is non-fatal.
"""

import httpx
import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ── Mapbox ────────────────────────────────────────────────────────
MAPBOX_URL     = "https://api.mapbox.com/geocoding/v5/mapbox.places"
MAPBOX_API_KEY = os.getenv("MAPBOX_API_KEY")

# ── Nominatim (OpenStreetMap) ─────────────────────────────────────
NOMINATIM_URL     = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "ProConnect-Clone/1.0 (internship project)"}


async def geocode_suburb_nominatim(
    suburb: str,
    state: Optional[str] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocode an Australian suburb using Nominatim (free, no API key).
    Used for job wizard AND as fallback for tradie profile if Mapbox fails.
    """
    if not suburb:
        return None, None

    parts = [suburb.strip()]
    if state:
        parts.append(state.strip())
    parts.append("Australia")
    query = ", ".join(parts)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "q":              query,
                    "format":         "json",
                    "limit":          1,
                    "countrycodes":   "au",
                    "addressdetails": 0,
                },
                headers=NOMINATIM_HEADERS,
            )
            response.raise_for_status()
            results = response.json()

            if results:
                lat = float(results[0]["lat"])
                lng = float(results[0]["lon"])
                logger.info(f"Nominatim geocoded '{query}' -> ({lat}, {lng})")
                return lat, lng
            else:
                logger.warning(f"Nominatim: no results for '{query}'")
                return None, None

    except httpx.TimeoutException:
        logger.warning(f"Nominatim timeout for '{query}' — skipping")
        return None, None
    except Exception as e:
        logger.error(f"Nominatim error for '{query}': {e}")
        return None, None


async def geocode_suburb_mapbox(
    suburb: str,
    state: Optional[str] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocode an Australian suburb using Mapbox.
    Used for tradie profile setup.
    Falls back to Nominatim if Mapbox key missing or request fails.
    """
    if not suburb:
        return None, None

    if not MAPBOX_API_KEY:
        logger.warning("MAPBOX_API_KEY not set — falling back to Nominatim")
        return await geocode_suburb_nominatim(suburb, state)

    parts = [suburb.strip()]
    if state:
        parts.append(state.strip())
    parts.append("Australia")
    query = ", ".join(parts)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{MAPBOX_URL}/{query}.json",
                params={
                    "access_token": MAPBOX_API_KEY,
                    "country":      "AU",
                    "types":        "place,locality,neighborhood,postcode",
                    "limit":        1,
                },
            )
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            if features:
                # Mapbox returns [lng, lat] — note reversed order
                lng, lat = features[0]["geometry"]["coordinates"]
                logger.info(f"Mapbox geocoded '{query}' -> ({lat}, {lng})")
                return lat, lng
            else:
                logger.warning(f"Mapbox: no results for '{query}' — trying Nominatim")
                return await geocode_suburb_nominatim(suburb, state)

    except httpx.TimeoutException:
        logger.warning(f"Mapbox timeout for '{query}' — trying Nominatim")
        return await geocode_suburb_nominatim(suburb, state)
    except Exception as e:
        logger.error(f"Mapbox error for '{query}': {e} — trying Nominatim")
        return await geocode_suburb_nominatim(suburb, state)


# ── Convenience aliases ───────────────────────────────────────────
# For tradie profile — Mapbox with Nominatim fallback
geocode_tradie_suburb = geocode_suburb_mapbox

# For job wizard — Nominatim only (free)
geocode_suburb = geocode_suburb_nominatim