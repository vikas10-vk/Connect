from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user
from dotenv import load_dotenv
import stripe
import os

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

CREDIT_PACKAGES = [
    {"id": "pack_10",  "credits": 10,  "amount": 4900,  "label": "10 Credits — $49"},
    {"id": "pack_25",  "credits": 25,  "amount": 9900,  "label": "25 Credits — $99"},
    {"id": "pack_50",  "credits": 50,  "amount": 17900, "label": "50 Credits — $179"},
]

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.get("/packages")
async def get_packages():
    return CREDIT_PACKAGES


@router.post("/create-checkout/{package_id}")
async def create_checkout(
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can purchase credits")

    package = next((p for p in CREDIT_PACKAGES if p["id"] == package_id), None)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Create your tradie profile first")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "aud",
                    "product_data": {"name": package["label"]},
                    "unit_amount": package["amount"],
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="http://localhost:3000/tradie/credits/success",
            cancel_url="http://localhost:3000/tradie/credits",
            metadata={
                "tradie_id": profile.id,
                "credits":   str(package["credits"]),
                "user_id":   current_user.id,
            }
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session  = event["data"]["object"]
        metadata = session.get("metadata", {})
        tradie_id = metadata.get("tradie_id")
        credits   = int(metadata.get("credits", 0))

        if tradie_id and credits:
            result = await db.execute(
                select(TradieProfile).where(TradieProfile.id == tradie_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                profile.credits += credits
                db.add(profile)
                await db.commit()
                print(f"Added {credits} credits to tradie {tradie_id}")

    return {"received": True}