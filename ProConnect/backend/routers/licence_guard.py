
from fastapi import APIRouter
from pydantic import BaseModel

from services.compliance_service import get_licence_requirements

router = APIRouter(prefix="/api/v1/licence-guard", tags=["LicenceGuard"])


class LicenceCheckRequest(BaseModel):
    state:    str
    category: str
    job_type: str | None = "residential"


@router.post("/check")
async def check_licence(body: LicenceCheckRequest):
    """
    Check licence and compliance requirements for a given
    state + category + job_type combination.
    No auth required — public endpoint.
    """
    result = get_licence_requirements(
        state    = body.state,
        category = body.category,
        job_type = body.job_type or "residential",
    )
    return result


@router.get("/states")
async def get_supported_states():
    return ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT"]


@router.get("/categories")
async def get_supported_categories():
    return [
        "Electrical", "Plumbing", "Building", "Roofing",
        "Air Conditioning", "Gas System", "Carpentry",
        "Painting", "Landscaping", "Cleaning", "Pest Control",
        "Solar Panels", "Fencing", "Tiling", "Concreting",
    ]
