"""
Notification service — 3 layers for inquiry notifications:

  Layer 1: WebSocket  — instant if tradie is online (always attempted)
  Layer 2: SendGrid   — email fallback (skipped if SENDGRID_API_KEY not set)
  Layer 3: Twilio     — SMS fallback  (skipped if TWILIO_* keys not set)

All layers are non-blocking — a failure in one never blocks the others.
Zero code changes needed when you add SendGrid/Twilio keys later.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Env keys ──────────────────────────────────────────────────────
SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")


async def notify_tradie_new_inquiry(
    tradie_user_id:   str,
    tradie_name:      str,
    tradie_email:     str,
    tradie_phone:     Optional[str],
    sender_name:      str,
    sender_email:     str,
    sender_phone:     Optional[str],
    message:          str,
    inquiry_id:       str,
) -> None:
    """
    Notify a tradie about a new inquiry via all available channels.
    Each channel is independent — failure in one does not affect others.
    """

    # ── Layer 1: WebSocket (instant, if tradie is online) ─────────
    await _notify_websocket(
        tradie_user_id=tradie_user_id,
        sender_name=sender_name,
        message=message,
        inquiry_id=inquiry_id,
    )

    # ── Layer 2: SendGrid email ───────────────────────────────────
    await _notify_email(
        tradie_name=tradie_name,
        tradie_email=tradie_email,
        sender_name=sender_name,
        sender_email=sender_email,
        sender_phone=sender_phone,
        message=message,
    )

    # ── Layer 3: Twilio SMS ───────────────────────────────────────
    await _notify_sms(
        tradie_phone=tradie_phone,
        sender_name=sender_name,
        message=message,
    )


async def _notify_websocket(
    tradie_user_id: str,
    sender_name:    str,
    message:        str,
    inquiry_id:     str,
) -> None:
    """Send real-time WebSocket notification if tradie is connected."""
    try:
        from routers.websocket import manager
        await manager.send_to_tradie(tradie_user_id, {
            "type":        "new_inquiry",
            "inquiry_id":  inquiry_id,
            "sender_name": sender_name,
            "message":     message[:100],   # preview only
        })
        logger.info(f"WebSocket notification sent to tradie {tradie_user_id}")
    except Exception as e:
        # Tradie not connected — silent, this is expected
        logger.debug(f"WebSocket notification skipped (tradie offline): {e}")


async def _notify_email(
    tradie_name:  str,
    tradie_email: str,
    sender_name:  str,
    sender_email: str,
    sender_phone: Optional[str],
    message:      str,
) -> None:
    """Send email via SendGrid. Skipped if SENDGRID_API_KEY not configured."""
    if not SENDGRID_API_KEY:
        logger.info("SendGrid skipped — SENDGRID_API_KEY not set")
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        phone_line = f"Phone: {sender_phone}" if sender_phone else ""

        email_body = f"""
Hi {tradie_name},

You have a new inquiry from {sender_name}!

--- Inquiry Details ---
From:    {sender_name}
Email:   {sender_email}
{phone_line}

Message:
{message}
-----------------------

Log in to your ProConnect dashboard to respond.
        """.strip()

        mail = Mail(
            from_email="noreply@proconnect.com.au",
            to_emails=tradie_email,
            subject=f"New inquiry from {sender_name} — ProConnect",
            plain_text_content=email_body,
        )

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        response = sg.send(mail)
        logger.info(f"SendGrid email sent to {tradie_email} — status {response.status_code}")

    except ImportError:
        logger.warning("sendgrid package not installed — pip install sendgrid")
    except Exception as e:
        logger.error(f"SendGrid email failed: {e}")


async def _notify_sms(
    tradie_phone: Optional[str],
    sender_name:  str,
    message:      str,
) -> None:
    """Send SMS via Twilio. Skipped if TWILIO_* keys not configured."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        logger.info("Twilio skipped — TWILIO_* keys not set")
        return

    if not tradie_phone:
        logger.info("Twilio skipped — tradie has no phone number")
        return

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        sms_body = (
            f"ProConnect: New inquiry from {sender_name}. "
            f"Message: {message[:80]}... "
            f"Log in to respond."
        )

        client.messages.create(
            body=sms_body,
            from_=TWILIO_FROM_NUMBER,
            to=tradie_phone,
        )
        logger.info(f"Twilio SMS sent to {tradie_phone}")

    except ImportError:
        logger.warning("twilio package not installed — pip install twilio")
    except Exception as e:
        logger.error(f"Twilio SMS failed: {e}")