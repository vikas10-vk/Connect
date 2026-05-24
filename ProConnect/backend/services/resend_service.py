"""
backend/services/resend_service.py

UPDATED — four new email functions added at the bottom:
  send_cert_expiry_reminder_email    Tiered reminder: 30/14/7/1 days before cert expiry
  send_cert_expired_email            Cert has expired — bookings paused for that category
  send_insurance_expiry_reminder_email  Tiered reminder for insurance expiry
  send_insurance_expired_email          Insurance expired — ENTIRE business paused

All existing functions are preserved exactly as written.
"""

import logging
import os
from datetime import date

import httpx
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=False,
)

logger = logging.getLogger(__name__)

RESEND_API_KEY    = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()
APP_NAME          = os.getenv("APP_NAME", "ProConnect").strip()
APP_BASE_URL      = os.getenv("APP_BASE_URL", "http://localhost:3000").strip().rstrip("/")

RESEND_API_URL = "https://api.resend.com/emails"


# ── Core send helper ──────────────────────────────────────────────────────────

async def _send_raw_email(to_email: str, subject: str, html: str, text: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning("[resend] No API key — printing to stdout (dev mode)")
        print(f"\n{'='*60}\n[DEV EMAIL] To: {to_email}\nSubject: {subject}\n\n{text}\n{'='*60}\n", flush=True)
        return True
    payload = {
        "from":    f"{APP_NAME} <{RESEND_FROM_EMAIL}>",
        "to":      [to_email],
        "subject": subject,
        "html":    html,
        "text":    text,
    }
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(RESEND_API_URL, json=payload, headers=headers)
        if resp.status_code in (200, 201, 202):
            logger.info("[resend] sent '%s' to %s", subject, to_email)
            return True
        logger.error("[resend] failed (%s) for %s: %s", resp.status_code, to_email, resp.text[:200])
        return False
    except Exception as e:
        logger.exception("[resend] exception sending to %s: %s", to_email, e)
        return False


# ── Template helpers ──────────────────────────────────────────────────────────

def _base_html(body_html: str, accent_color: str = "#C5563A") -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#FAF7F1;font-family:'Inter',-apple-system,sans-serif;">
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#FAF7F1;padding:40px 20px;">
    <tr><td align="center">
      <table role="presentation" cellpadding="0" cellspacing="0"
             style="max-width:480px;width:100%;background:#FFF;border-radius:16px;
                    border:1px solid #E8E2D4;box-shadow:0 1px 3px rgba(26,26,26,0.05);">
        <tr><td style="padding:32px 36px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
            <tr>
              <td style="background:{accent_color};width:34px;height:34px;border-radius:9px;
                          text-align:center;color:#FFF;font-weight:700;font-size:17px;
                          font-family:Georgia,serif;line-height:34px;">P</td>
              <td style="padding-left:10px;font-family:Georgia,serif;font-size:17px;
                          font-weight:500;color:#1A1A1A;">{APP_NAME}</td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 36px 32px;">{body_html}</td></tr>
        <tr><td style="padding:18px 36px;border-top:1px solid #EFEAE0;">
          <p style="margin:0;font-size:11.5px;color:#8A8882;line-height:1.6;">
            {APP_NAME} — Australia's trusted tradie marketplace.<br>
            Need help? Reply to this email and our team will get back to you.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _btn(text: str, url: str, color: str = "#C5563A") -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px;">
      <tr><td style="background:{color};border-radius:10px;padding:13px 28px;text-align:center;">
        <a href="{url}" style="color:#fff;text-decoration:none;font-weight:700;font-size:14px;white-space:nowrap;">{text}</a>
      </td></tr></table>"""


def _box(text: str, color: str = "#C5563A", bg: str = "#F5EDE9") -> str:
    return f"""<div style="background:{bg};border:1px solid {color}33;border-radius:12px;
                padding:16px 20px;margin:20px 0;">
      <p style="margin:0;font-size:13.5px;line-height:1.7;color:#1A1A1A;">{text}</p></div>"""


def _first(name: str) -> str:
    return (name or "there").split()[0]


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING EMAIL FUNCTIONS — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

async def send_otp_email(to_email: str, code: str, full_name: str = "") -> bool:
    name = _first(full_name)
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Your verification code</h1>
      <p style="margin:0 0 28px;font-size:14.5px;line-height:1.65;color:#4A4A48;">
        G'day {name}, here's your one-time code to verify your {APP_NAME} account.
      </p>
      <div style="background:#F4EEDD;border:1px solid #E6D9B5;border-radius:12px;padding:20px;text-align:center;margin-bottom:24px;">
        <p style="margin:0 0 6px;font-size:11px;font-weight:600;color:#A68A4E;text-transform:uppercase;letter-spacing:0.14em;">Verification code</p>
        <p style="margin:0;font-family:'Courier New',monospace;font-size:38px;font-weight:700;color:#1A1A1A;letter-spacing:0.18em;">{code}</p>
      </div>
      <p style="margin:0;font-size:13px;color:#8A8882;line-height:1.6;">
        Expires in <strong style="color:#4A4A48;">10 minutes</strong>. If you didn't request this, ignore this email.
      </p>"""
    text = f"G'day {name},\n\nYour {APP_NAME} code is: {code}\n\nExpires in 10 minutes.\n\n— The {APP_NAME} team"
    return await _send_raw_email(to_email, f"Your {APP_NAME} verification code: {code}", _base_html(body), text)


async def send_admin_note_email(
    to_email: str,
    subject: str,
    message: str,
    *,
    full_name: str = "",
    accent_color: str = "#2E7D5A",
) -> bool:
    name = _first(full_name)
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:24px;font-weight:500;color:#1A1A1A;">A note from {APP_NAME}</h1>
      <p style="margin:0 0 18px;font-size:14.5px;line-height:1.65;color:#4A4A48;">G'day {name},</p>
      {_box(message, accent_color, "#F4F8F5")}
      <p style="margin:18px 0 0;font-size:13px;color:#8A8882;line-height:1.6;">
        Thanks for helping keep the {APP_NAME} marketplace trustworthy.
      </p>"""
    text = f"G'day {name},\n\n{message}\n\n- The {APP_NAME} team"
    return await _send_raw_email(to_email, subject, _base_html(body, accent_color), text)


async def send_tradie_approved_email(to_email: str, full_name: str, business_name: str) -> bool:
    name = _first(full_name)
    url = f"{APP_BASE_URL}/tradie/dashboard"
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">You're verified! 🎉</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, <strong>{business_name}</strong> has been approved on {APP_NAME}. Your profile is now live and you'll start receiving job leads.
      </p>
      {_box("✅ Your account is now active<br>📍 Leads will arrive based on your service area<br>💳 Check your credit balance in the dashboard", "#2E7D5A", "#E8F5EE")}
      {_btn("Open My Dashboard", url, "#2E7D5A")}"""
    text = f"G'day {name},\n\n'{business_name}' has been approved on {APP_NAME}.\n\nDashboard: {url}\n\n— The {APP_NAME} team"
    return await _send_raw_email(to_email, f"✅ You're verified on {APP_NAME}! Welcome aboard, {name}", _base_html(body, "#2E7D5A"), text)


async def send_tradie_rejected_email(to_email: str, full_name: str, business_name: str, notes: str | None = None) -> bool:
    name = _first(full_name)
    notes_block = _box(f"<strong>Reason:</strong><br>{notes}", "#B85C00", "#FFF9F0") if notes else ""
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Application update for {business_name}</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, after reviewing your application we're unable to approve it at this time.
      </p>
      {notes_block}
      <p style="margin:20px 0 0;font-size:14px;line-height:1.7;color:#4A4A48;">Reply to this email if you'd like to discuss your application.</p>"""
    text = (f"G'day {name},\n\nWe reviewed '{business_name}' and can't approve it at this time.\n\n"
            + (f"Reason: {notes}\n\n" if notes else "") + f"Reply to discuss.\n\n— The {APP_NAME} team")
    return await _send_raw_email(to_email, f"Update on your {APP_NAME} application", _base_html(body), text)


async def send_tradie_needs_documents_email(to_email: str, full_name: str, business_name: str, notes: str | None = None) -> bool:
    name = _first(full_name)
    url = f"{APP_BASE_URL}/tradie/dashboard"
    notes_block = _box(f"<strong>What we need:</strong><br>{notes}", "#0077AA", "#E0F4FF") if notes else ""
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Action required: additional documents needed</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, we're reviewing <strong>{business_name}</strong> and need more information before approving.
      </p>
      {notes_block}
      <p style="margin:20px 0;font-size:14px;line-height:1.7;color:#4A4A48;">Reply to this email with the required documents. We'll complete your review within 1 business day.</p>
      {_btn("Go to Dashboard", url, "#0077AA")}"""
    text = (f"G'day {name},\n\nWe need more info for '{business_name}'.\n\n"
            + (f"What we need: {notes}\n\n" if notes else "") + f"Reply with the documents.\n\nDashboard: {url}\n\n— The {APP_NAME} team")
    return await _send_raw_email(to_email, f"Action required: documents needed for your {APP_NAME} application", _base_html(body, "#0077AA"), text)


async def send_tradie_suspended_email(to_email: str, full_name: str, business_name: str, reason: str | None = None) -> bool:
    name = _first(full_name)
    reason_block = _box(f"<strong>Reason:</strong><br>{reason}", "#A33030", "#FFF5F5") if reason else ""
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Your {APP_NAME} account has been suspended</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, your account for <strong>{business_name}</strong> has been suspended. You will not receive new leads while under review.
      </p>
      {reason_block}
      <p style="margin:20px 0 0;font-size:14px;line-height:1.7;color:#4A4A48;">Reply to this email to appeal. Our team responds within 2 business days.</p>"""
    text = (f"G'day {name},\n\nYour {APP_NAME} account for '{business_name}' has been suspended.\n\n"
            + (f"Reason: {reason}\n\n" if reason else "") + f"Reply to appeal.\n\n— The {APP_NAME} team")
    return await _send_raw_email(to_email, f"Your {APP_NAME} account has been suspended", _base_html(body), text)


async def send_review_approved_email(to_email: str, full_name: str, tradie_business_name: str, tradie_profile_id: str) -> bool:
    name = _first(full_name)
    url = f"{APP_BASE_URL}/tradies/{tradie_profile_id}"
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Your review is now live</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, your review of <strong>{tradie_business_name}</strong> has been approved and is now visible on their public profile.
      </p>
      {_box("Your review helps other homeowners make informed decisions. Thank you for sharing your experience.", "#2E7D5A", "#E8F5EE")}
      {_btn("View Profile", url, "#2E7D5A")}"""
    text = f"G'day {name},\n\nYour review of '{tradie_business_name}' is now live.\n\nProfile: {url}\n\n— The {APP_NAME} team"
    return await _send_raw_email(to_email, f"Your review of {tradie_business_name} is now live", _base_html(body, "#2E7D5A"), text)


async def send_review_rejected_email(to_email: str, full_name: str, tradie_business_name: str) -> bool:
    name = _first(full_name)
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Update on your review</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, our moderation team has decided not to publish your review of <strong>{tradie_business_name}</strong>.
      </p>
      <p style="margin:0;font-size:14px;line-height:1.7;color:#4A4A48;">If you have questions or would like to resubmit, please reply to this email.</p>"""
    text = f"G'day {name},\n\nYour review of '{tradie_business_name}' was not published.\n\nReply with questions.\n\n— The {APP_NAME} team"
    return await _send_raw_email(to_email, f"Update on your {APP_NAME} review", _base_html(body), text)


async def send_no_tradies_email(to_email: str, full_name: str, job_title: str, suburb: str) -> bool:
    name = _first(full_name)
    url = f"{APP_BASE_URL}/dashboard"
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">We're finding you a tradie</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, your job <strong>"{job_title}"</strong> in {suburb} has been received.
        We don't have a tradie available in your area <em>right now</em>, but we're actively
        looking and will notify you the moment one becomes available.
      </p>
      {_box("✅ Your job is saved and active<br>🔔 We'll email you as soon as a tradie is matched<br>⏱ Most homeowners hear back within 24 hours", "#0077AA", "#E0F4FF")}
      <p style="margin:20px 0 0;font-size:13px;color:#8A8882;line-height:1.6;">
        You can view your job or make changes from your dashboard at any time.
      </p>
      {_btn("View My Job", url, "#0077AA")}"""
    text = (f"G'day {name},\n\nYour job '{job_title}' in {suburb} is saved and active.\n\n"
            f"No tradies available right now — we'll email you as soon as one matches.\n"
            f"Most homeowners hear back within 24 hours.\n\nDashboard: {url}\n\n— The {APP_NAME} team")
    return await _send_raw_email(to_email, f"We're finding you a tradie for your {job_title} job", _base_html(body, "#0077AA"), text)


async def send_uncategorised_received_email(
    to_email: str, full_name: str, description_excerpt: str,
) -> bool:
    """
    Sent to a homeowner immediately after they submit a 'service not listed'
    request. Tells them honestly that a human will look at it within 24h.
    """
    name = _first(full_name)
    url = f"{APP_BASE_URL}/dashboard"
    snippet = (description_excerpt or "").strip().replace("\n", " ")
    if len(snippet) > 220:
        snippet = snippet[:220] + "..."
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">We've received your request</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, thanks for telling us what you need. Your request looks like
        something outside our standard service list, so a real person on our team
        will read it and get back to you within 24 hours.
      </p>
      {_box(snippet or "No description supplied.", "#0077AA", "#E0F4FF")}
      <p style="margin:20px 0 0;font-size:13px;color:#8A8882;line-height:1.6;">
        We'll either match you with a tradie who can help, or honestly let you know
        if it's not something we cover yet.
      </p>
      {_btn("View Dashboard", url, "#0077AA")}"""
    text = (
        f"G'day {name},\n\n"
        f"We've received your service request:\n\n  {snippet or '(no description supplied)'}\n\n"
        f"This looks outside our standard service list, so a person on our team "
        f"will read it and get back to you within 24 hours.\n\n"
        f"Dashboard: {url}\n\n— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        "We've received your service request — we'll respond within 24h",
        _base_html(body, "#0077AA"),
        text,
    )


async def send_uncategorised_not_supported_email(
    to_email: str, full_name: str, description_excerpt: str,
    admin_note: str | None = None,
) -> bool:
    """
    Sent when admin reviews an uncategorised request and decides the platform
    can't help with it. Polite, honest, with optional admin context.
    """
    name = _first(full_name)
    snippet = (description_excerpt or "").strip().replace("\n", " ")
    if len(snippet) > 220:
        snippet = snippet[:220] + "..."

    note_block = ""
    if admin_note:
        safe_note = admin_note.strip().replace("\n", "<br>")
        note_block = (
            f'<div style="background:#F8F5EE;border:1px solid #E6D9B5;border-radius:12px;'
            f'padding:14px 18px;margin:18px 0;font-size:13.5px;color:#1A1A1A;line-height:1.6;">'
            f'<strong>From our team:</strong><br>{safe_note}</div>'
        )

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Sorry — we can't help with this one</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, thanks again for telling us what you needed. Unfortunately
        this service is outside what {APP_NAME} currently covers in your area.
      </p>
      {_box(snippet or "No description supplied.", "#8A8882", "#F8F5EE")}
      {note_block}
      <p style="margin:20px 0 0;font-size:13px;color:#8A8882;line-height:1.6;">
        We've logged your request so we know what services people are looking for.
        If we add this service in future we'll let you know.
      </p>"""
    text_note = f"\n\nFrom our team: {admin_note}\n" if admin_note else "\n"
    text = (
        f"G'day {name},\n\n"
        f"Thanks for telling us what you needed:\n\n  {snippet or '(no description supplied)'}\n\n"
        f"Unfortunately this service is outside what {APP_NAME} currently covers in your area."
        f"{text_note}"
        f"We've logged your request so we know what services people are looking for. "
        f"If we add this service in future we'll let you know.\n\n"
        f"— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"About your {APP_NAME} service request",
        _base_html(body, "#8A8882"),
        text,
    )


async def send_job_disputed_to_tradie_email(
    to_email: str, full_name: str, business_name: str,
    job_title: str, suburb: str, dispute_reason: str | None = None,
) -> bool:
    """
    Sent the moment a homeowner raises a dispute. The tradie needs to know
    immediately, see the exact reason, and know what action to take next.
    """
    name = _first(full_name)
    url = f"{APP_BASE_URL}/tradie/dashboard"
    reason_html = ""
    reason_text = ""
    if dispute_reason and dispute_reason.strip():
        safe = dispute_reason.strip().replace("\n", "<br>")
        reason_html = (
            f'<div style="background:#FFF5F5;border:1px solid #A3303033;border-radius:12px;'
            f'padding:14px 18px;margin:18px 0;font-size:14px;color:#1A1A1A;line-height:1.6;">'
            f'<strong>Homeowner\'s reason:</strong><br>{safe}</div>'
        )
        reason_text = f"\n\nHomeowner's reason:\n  {dispute_reason.strip()}\n"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">A homeowner has disputed your job</h1>
      <p style="margin:0 0 16px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the homeowner has raised a dispute on <strong>"{job_title}"</strong>
        in {suburb}. The job is now paused while our team reviews what happened.
      </p>
      {reason_html}
      <div style="background:#FFF9F0;border:1px solid #B85C0033;border-radius:12px;padding:14px 18px;margin:18px 0;font-size:13.5px;color:#1A1A1A;line-height:1.6;">
        <strong>What happens next</strong><br>
        1. Our admin team will read the dispute and contact both of you within 2 business days.<br>
        2. Upload any supporting photos, messages, or invoices via your dashboard now -- it strengthens your side.<br>
        3. Payment release is paused until the dispute is resolved.
      </div>
      {_btn("View Job & Upload Evidence", url, "#A33030")}
      <p style="margin:20px 0 0;font-size:12.5px;color:#8A8882;line-height:1.6;">
        If you believe the dispute is unfair, you can also reply to this email with your side of the story.
      </p>"""
    text = (
        f"G'day {name},\n\n"
        f"The homeowner has disputed your job '{job_title}' in {suburb}. "
        f"The job is now paused while our team reviews."
        f"{reason_text}\n"
        f"What to do:\n"
        f"1. Admin will contact both parties within 2 business days.\n"
        f"2. Upload supporting evidence via your dashboard: {url}\n"
        f"3. Payment release is paused until resolved.\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"Dispute raised on {job_title} -- {APP_NAME}",
        _base_html(body, "#A33030"),
        text,
    )


async def send_dispute_response_posted_email(
    to_email: str, to_name: str, job_title: str,
    poster_role: str,         # 'homeowner' or 'tradie' -- the role of who just posted
    response_excerpt: str,
) -> bool:
    """
    Sent to the OPPOSITE party whenever someone posts a dispute response, so
    nobody is left in the dark during the mediation window.
    """
    name = _first(to_name)
    url  = f"{APP_BASE_URL}/dashboard" if poster_role == "tradie" else f"{APP_BASE_URL}/tradie/dashboard"
    poster_label = "the tradie" if poster_role == "tradie" else "the homeowner"
    snippet = (response_excerpt or "").strip().replace("\n", " ")
    if len(snippet) > 240:
        snippet = snippet[:240] + "..."

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:24px;font-weight:500;color:#1A1A1A;">{poster_label.title()} has added to the dispute</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#4A4A48;">
        G'day {name}, on your job <strong>"{job_title}"</strong>, {poster_label} has just posted a response to the dispute. Our admin team is reviewing both sides and will reach a decision shortly.
      </p>
      {_box(snippet or "(no message text)", "#0077AA", "#E0F4FF")}
      <p style="margin:16px 0 0;font-size:13px;color:#4A4A48;line-height:1.6;">
        You can read the full conversation and add anything you forgot to mention from your dashboard.
      </p>
      {_btn("View dashboard", url, "#0077AA")}"""
    text = (
        f"G'day {name},\n\n"
        f"{poster_label.title()} has added to the dispute on '{job_title}':\n\n  {snippet or '(no message)'}\n\n"
        f"Admin is reviewing both sides. You can add more context from your dashboard:\n{url}\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email, f"New response on your dispute -- {APP_NAME}", _base_html(body, "#0077AA"), text,
    )


async def send_dispute_resolved_to_homeowner_email(
    to_email: str, full_name: str, job_title: str,
    resolution: str, admin_note: str | None = None,
    refund_amount: float | None = None,
) -> bool:
    """
    Sent when admin closes a dispute. The wording adapts to which of the four
    resolution paths admin chose, so the homeowner gets a concrete answer rather
    than a generic "resolved" message.
    """
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/dashboard"

    if resolution == "refund_homeowner":
        headline = "Your dispute has been resolved -- full refund"
        accent   = "#2E7D5A"
        summary  = "We sided with you. A full refund is being processed and you should see it in 3-5 business days."
    elif resolution == "partial_refund":
        amt = f"${refund_amount:,.2f}" if refund_amount else "a partial refund"
        headline = f"Your dispute has been resolved -- {amt} refund"
        accent   = "#2E7D5A"
        summary  = f"We reviewed both sides and decided on {amt}. The refund is being processed and should land in 3-5 business days."
    elif resolution == "side_tradie":
        headline = "Your dispute has been resolved -- work accepted"
        accent   = "#0077AA"
        summary  = "After reviewing the evidence from both sides, our team determined the work was completed satisfactorily. No refund will be issued."
    elif resolution == "redo_work":
        headline = "Your dispute has been resolved -- tradie is returning to fix the work"
        accent   = "#B85C00"
        summary  = (
            "We've reviewed both sides and instructed the tradie to return and redo the work. "
            "Your job is now active again. The tradie will contact you to arrange a return visit. "
            "Once they mark it complete, you'll be asked to confirm — and you can raise another "
            "dispute at that point if you're still not satisfied."
        )
    else:
        headline = "Your dispute has been resolved"
        accent   = "#0077AA"
        summary  = "Our team has reviewed your dispute and reached a decision."

    note_block = ""
    note_text  = ""
    if admin_note and admin_note.strip():
        safe = admin_note.strip().replace("\n", "<br>")
        note_block = (
            f'<div style="background:#F8F5EE;border:1px solid #E6D9B5;border-radius:12px;'
            f'padding:14px 18px;margin:16px 0;font-size:13.5px;color:#1A1A1A;line-height:1.6;">'
            f'<strong>Admin\'s decision note:</strong><br>{safe}</div>'
        )
        note_text = f"\n\nAdmin's decision note:\n  {admin_note.strip()}\n"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">{headline}</h1>
      <p style="margin:0 0 18px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, regarding your job <strong>"{job_title}"</strong>:
      </p>
      {_box(summary, accent, "#F4F8F5" if accent == "#2E7D5A" else "#E0F4FF" if accent == "#0077AA" else "#FFF3E0")}
      {note_block}
      {_btn("View Job", url, accent)}
      <p style="margin:24px 0 0;font-size:12px;color:#8A8882;line-height:1.6;">
        If you have questions about this decision, reply to this email and our team will follow up.
      </p>"""
    text = (
        f"G'day {name},\n\n"
        f"{headline}\n\n"
        f"Job: {job_title}\n"
        f"Decision: {summary}"
        f"{note_text}\n"
        f"View your dashboard: {url}\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email, f"{headline} -- {APP_NAME}", _base_html(body, accent), text,
    )


async def send_dispute_resolved_to_tradie_email(
    to_email: str, full_name: str, business_name: str, job_title: str,
    resolution: str, admin_note: str | None = None,
    refund_amount: float | None = None,
) -> bool:
    """Same four resolution paths, framed from the tradie's perspective."""
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/tradie/dashboard"

    if resolution == "refund_homeowner":
        headline = "Dispute resolved -- full refund issued to homeowner"
        accent   = "#A33030"
        summary  = ("After reviewing both sides, our team decided to refund the homeowner in full. "
                    "Payment for this job will not be released. The job is now closed.")
    elif resolution == "partial_refund":
        amt = f"${refund_amount:,.2f}" if refund_amount else "a partial refund"
        headline = f"Dispute resolved -- {amt} refund to homeowner"
        accent   = "#B85C00"
        summary  = (f"After reviewing both sides, our team decided on {amt} back to the homeowner. "
                    f"The remainder of your payment will be released. The job is now closed.")
    elif resolution == "side_tradie":
        headline = "Dispute resolved -- in your favour"
        accent   = "#2E7D5A"
        summary  = ("We reviewed the evidence and determined your work was completed satisfactorily. "
                    "Payment is being released to you in full.")
    elif resolution == "redo_work":
        headline = "Dispute resolved -- please return to finish the work"
        accent   = "#B85C00"
        summary  = ("The job has been re-opened. Please contact the homeowner to arrange a return visit "
                    "and complete/redo the work as discussed. Payment will be released once the homeowner "
                    "confirms the work is done.")
    else:
        headline = "Dispute resolved"
        accent   = "#0077AA"
        summary  = "Our team has reached a decision on this dispute."

    note_block = ""
    note_text  = ""
    if admin_note and admin_note.strip():
        safe = admin_note.strip().replace("\n", "<br>")
        note_block = (
            f'<div style="background:#F8F5EE;border:1px solid #E6D9B5;border-radius:12px;'
            f'padding:14px 18px;margin:16px 0;font-size:13.5px;color:#1A1A1A;line-height:1.6;">'
            f'<strong>Admin\'s decision note:</strong><br>{safe}</div>'
        )
        note_text = f"\n\nAdmin's decision note:\n  {admin_note.strip()}\n"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">{headline}</h1>
      <p style="margin:0 0 18px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, regarding the dispute on <strong>"{job_title}"</strong>:
      </p>
      {_box(summary, accent, "#FFF5F5" if accent == "#A33030" else "#E8F5EE" if accent == "#2E7D5A" else "#FFF3E0" if accent == "#B85C00" else "#E0F4FF")}
      {note_block}
      {_btn("View Job", url, accent)}
      <p style="margin:24px 0 0;font-size:12px;color:#8A8882;line-height:1.6;">
        If you wish to appeal this decision, reply to this email within 7 days with any new evidence.
      </p>"""
    text = (
        f"G'day {name},\n\n"
        f"{headline}\n\n"
        f"Job: {job_title}\n"
        f"Decision: {summary}"
        f"{note_text}\n"
        f"Dashboard: {url}\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email, f"{headline} -- {APP_NAME}", _base_html(body, accent), text,
    )


async def send_stale_job_email(to_email: str, full_name: str, job_title: str, lead_count: int) -> bool:
    name = _first(full_name)
    url = f"{APP_BASE_URL}/dashboard"
    word = "tradie" if lead_count == 1 else "tradies"
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">Tradies are reviewing your job</h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, your job <strong>"{job_title}"</strong> has been sent to {lead_count} {word} in your area.
        They're reviewing the details and will submit quotes shortly — no action needed from you.
      </p>
      {_box("💡 <strong>Tip:</strong> Adding photos of the problem helps tradies quote more accurately and respond faster.", "#2E7D5A", "#E8F5EE")}
      <p style="margin:20px 0 0;font-size:13px;color:#8A8882;line-height:1.6;">
        You'll get an email the moment a quote arrives.
      </p>
      {_btn("View Job Status", url)}"""
    text = (f"G'day {name},\n\nYour job '{job_title}' has been sent to {lead_count} {word}.\n"
            f"They're reviewing and will quote soon — no action needed.\n\n"
            f"Tip: adding photos helps tradies respond faster.\n\nDashboard: {url}\n\n— The {APP_NAME} team")
    return await _send_raw_email(to_email, f"Update on your {job_title} job — tradies are reviewing", _base_html(body), text)


# ═══════════════════════════════════════════════════════════════════════════
# NEW EMAIL FUNCTIONS — Licence & Insurance Expiry
# ═══════════════════════════════════════════════════════════════════════════

# ── Cert expiry reminder (30 / 14 / 7 / 1 days) ──────────────────────────────

async def send_cert_expiry_reminder_email(
    to_email: str,
    full_name: str,
    business_name: str,
    category_name: str,
    expires_at: date,
    days_remaining: int,
) -> bool:
    """
    Sent to the business owner when a trade licence is approaching expiry.
    Tiered urgency: 30 days = informational, 7 days = warning, 1 day = urgent.
    Always links directly to the verification dashboard.
    """
    name         = _first(full_name)
    url          = f"{APP_BASE_URL}/tradie/dashboard"
    expiry_str   = expires_at.strftime("%-d %B %Y")

    # Subject and accent colour scale with urgency
    if days_remaining <= 1:
        urgency_word   = "tomorrow"
        subject_prefix = "⚠️ Urgent"
        accent         = "#A33030"
        box_color      = "#A33030"
        box_bg         = "#FFF5F5"
        urgency_note   = "Your bookings will be paused automatically if the licence is not renewed before expiry."
    elif days_remaining <= 7:
        urgency_word   = f"in {days_remaining} days"
        subject_prefix = "Action needed"
        accent         = "#B85C00"
        box_color      = "#B85C00"
        box_bg         = "#FFF9F0"
        urgency_note   = "Submit your updated licence number now so our team can verify it before the expiry date."
    else:
        urgency_word   = f"in {days_remaining} days"
        subject_prefix = "Heads up"
        accent         = "#A68A4E"
        box_color      = "#A68A4E"
        box_bg         = "#F4EEDD"
        urgency_note   = "Renew your licence and submit the updated number before it expires to keep receiving jobs without interruption."

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">
        Your {category_name} licence expires {urgency_word}
      </h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the <strong>{category_name}</strong> licence registered to
        <strong>{business_name}</strong> expires on <strong>{expiry_str}</strong>.
      </p>
      {_box(f"📋 Licence expiry: <strong>{expiry_str}</strong><br>⏱ Days remaining: <strong>{days_remaining}</strong><br><br>{urgency_note}", box_color, box_bg)}
      <p style="margin:0 0 8px;font-size:14px;line-height:1.7;color:#4A4A48;">
        To renew: visit your dashboard, go to <strong>Licences &amp; Certifications</strong>,
        and submit your updated licence number. Our team verifies within 1 business day.
      </p>
      {_btn("Update My Licence", url, accent)}
      <p style="margin:20px 0 0;font-size:12.5px;color:#8A8882;line-height:1.6;">
        Questions? Reply to this email and our team will help.
      </p>"""

    text = (
        f"G'day {name},\n\n"
        f"Your {category_name} licence for '{business_name}' expires on {expiry_str} ({days_remaining} days).\n\n"
        f"{urgency_note}\n\n"
        f"Update your licence: {url}\n\n"
        f"— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"{subject_prefix}: your {category_name} licence expires {urgency_word} — {APP_NAME}",
        _base_html(body, accent),
        text,
    )


# ── Cert expired (day 0) ──────────────────────────────────────────────────────

async def send_cert_expired_email(
    to_email: str,
    full_name: str,
    business_name: str,
    category_name: str,
) -> bool:
    """
    Sent when a trade licence reaches its expiry date and is auto-expired
    by the Celery beat task. If no other valid cert exists for this category,
    the tradie has been paused. This email tells them exactly what happened
    and what to do to get back online.
    """
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/tradie/dashboard"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">
        Your {category_name} licence has expired
      </h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the <strong>{category_name}</strong> licence registered to
        <strong>{business_name}</strong> has expired today.
      </p>
      {_box(
          "🔴 <strong>What this means</strong><br>"
          "Your account has been paused for this trade category. You will not receive "
          f"new leads for <strong>{category_name}</strong> jobs until a valid licence is verified.<br><br>"
          "✅ <strong>How to get back online</strong><br>"
          "1. Renew your licence with the relevant state authority<br>"
          "2. Submit your new licence number via the dashboard<br>"
          "3. Our team will verify and re-activate your account within 1 business day",
          "#A33030", "#FFF5F5"
      )}
      {_btn("Submit New Licence", url, "#A33030")}
      <p style="margin:20px 0 0;font-size:12.5px;color:#8A8882;line-height:1.6;">
        If you believe this is an error, reply to this email and our team will assist within 1 business day.
      </p>"""

    text = (
        f"G'day {name},\n\n"
        f"Your {category_name} licence for '{business_name}' has expired today.\n\n"
        f"Your account has been paused for this trade category.\n\n"
        f"To get back online:\n"
        f"1. Renew your licence with the relevant authority\n"
        f"2. Submit the new number at: {url}\n"
        f"3. Our team will verify within 1 business day\n\n"
        f"Questions? Reply to this email.\n\n"
        f"— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"Your {category_name} licence has expired — bookings paused",
        _base_html(body, "#A33030"),
        text,
    )


# ── Insurance expiry reminder (30 / 14 / 7 / 1 days) ─────────────────────────

async def send_insurance_expiry_reminder_email(
    to_email: str,
    full_name: str,
    business_name: str,
    insurance_label: str,
    expires_at: date,
    days_remaining: int,
) -> bool:
    """
    Sent to the business owner when an insurance policy is approaching expiry.
    Insurance expiry disables the ENTIRE business — all workers paused.
    Tone is more urgent than cert expiry even at 30 days because the
    consequence is more severe.
    """
    name       = _first(full_name)
    url        = f"{APP_BASE_URL}/tradie/dashboard"
    expiry_str = expires_at.strftime("%-d %B %Y")

    if days_remaining <= 1:
        urgency_word   = "tomorrow"
        subject_prefix = "⚠️ Urgent"
        accent         = "#A33030"
        box_color      = "#A33030"
        box_bg         = "#FFF5F5"
        consequence    = "Your entire business will be paused automatically — all workers will stop receiving jobs."
    elif days_remaining <= 7:
        urgency_word   = f"in {days_remaining} days"
        subject_prefix = "Action needed"
        accent         = "#B85C00"
        box_color      = "#B85C00"
        box_bg         = "#FFF9F0"
        consequence    = "If the policy lapses, all workers in your business will be paused immediately."
    else:
        urgency_word   = f"in {days_remaining} days"
        subject_prefix = "Reminder"
        accent         = "#A68A4E"
        box_color      = "#A68A4E"
        box_bg         = "#F4EEDD"
        consequence    = "Renew early — insurance verification takes up to 1 business day and an expired policy pauses your whole team."

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">
        Your {insurance_label} expires {urgency_word}
      </h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the <strong>{insurance_label}</strong> registered to
        <strong>{business_name}</strong> expires on <strong>{expiry_str}</strong>.
      </p>
      {_box(
          f"Policy expiry: <strong>{expiry_str}</strong><br>"
          f"Days remaining: <strong>{days_remaining}</strong><br><br>"
          f"{consequence}",
          box_color, box_bg
      )}
      <p style="margin:0 0 8px;font-size:14px;line-height:1.7;color:#4A4A48;">
        Renew your policy, then submit your new policy number and certificate of currency
        via the dashboard. Our team verifies within 1 business day.
      </p>
      {_btn("Update Insurance Details", url, accent)}
      <p style="margin:20px 0 0;font-size:12.5px;color:#8A8882;line-height:1.6;">
        Need help? Reply to this email and our team will assist.
      </p>"""

    text = (
        f"G'day {name},\n\n"
        f"Your {insurance_label} for '{business_name}' expires on {expiry_str} ({days_remaining} days).\n\n"
        f"{consequence}\n\n"
        f"Update your insurance details: {url}\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"{subject_prefix}: your {insurance_label} expires {urgency_word} -- {APP_NAME}",
        _base_html(body, accent),
        text,
    )


async def send_insurance_expired_email(
    to_email: str,
    full_name: str,
    business_name: str,
    insurance_label: str,
) -> bool:
    """Sent when insurance reaches expiry and the business is auto-disabled."""
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/tradie/dashboard"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">
        Your {insurance_label} has expired -- business paused
      </h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the <strong>{insurance_label}</strong> registered to
        <strong>{business_name}</strong> expired today.
      </p>
      {_box(
          "<strong>What this means</strong><br>"
          "Your entire business has been paused. All workers have stopped receiving job assignments "
          "until a valid insurance policy is verified.<br><br>"
          "<strong>How to get back online</strong><br>"
          "1. Renew your policy with your insurer<br>"
          "2. Submit your new policy number and certificate of currency via the dashboard<br>"
          "3. Our team will verify and re-activate your business within 1 business day",
          "#A33030", "#FFF5F5"
      )}
      {_btn("Submit New Policy", url, "#A33030")}
      <p style="margin:20px 0 0;font-size:12.5px;color:#8A8882;line-height:1.6;">
        If you believe this is an error, or your policy has already been renewed, reply to
        this email immediately and our team will prioritise your review.
      </p>"""

    text = (
        f"G'day {name},\n\n"
        f"Your {insurance_label} for '{business_name}' expired today.\n\n"
        f"Your entire business has been paused -- all workers have stopped receiving job assignments.\n\n"
        f"To get back online:\n"
        f"1. Renew your policy with your insurer\n"
        f"2. Submit the new policy number at: {url}\n"
        f"3. Our team will verify and re-activate your account within 1 business day.\n\n"
        f"Log in to submit: {url}"
    )

    return await _send_raw_email(
        to_email=to_email,
        subject=f"Action required: {insurance_label} expired for {business_name}",
        html=html,
        text=text,
    )


async def send_dispute_resolution_claimed_email(
    to_email: str, full_name: str, job_title: str, tradie_business_name: str,
) -> bool:
    """
    Sent to the homeowner when the tradie claims they have resolved the dispute.
    Prompts them to log in and either accept or reject the resolution.
    """
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/dashboard"
    headline = "The tradie says they\'ve fixed it — your response needed"
    accent   = "#2E7D5A"
    summary  = (
        f"<strong>{tradie_business_name}</strong> has marked the dispute on "
        f"<strong>\"{job_title}\"</strong> as resolved from their side. "
        "Please log in and let us know whether you agree."
    )
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">{headline}</h1>
      <p style="margin:0 0 18px;font-size:14.5px;line-height:1.7;color:#4A4A48;">G\'day {name},</p>
      {_box(summary, accent, "#E8F5EE")}
      <p style="margin:16px 0;font-size:14px;line-height:1.7;color:#4A4A48;">
        On your dashboard you\'ll see two options:<br>
        <strong>✅ Accept</strong> — the issue is fixed, job moves back to completed and you can confirm it.<br>
        <strong>❌ Still not right</strong> — you\'re not satisfied; the dispute stays open for further review.
      </p>
      {_btn("Go to Dashboard", url, accent)}
      <p style="margin:24px 0 0;font-size:12px;color:#8A8882;line-height:1.6;">
        If you have questions, reply to this email and our team will follow up.
      </p>"""
    text = (
        f"G\'day {name},\n\n"
        f"{tradie_business_name} says they\'ve resolved the dispute on \"{job_title}\".\n\n"
        f"Log in to accept (job moves back to completed) or reject (dispute stays open):\n"
        f"{url}\n\n"
        f"-- The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email, f"Action needed: tradie says dispute resolved — {APP_NAME}", _base_html(body, accent), text,
    )


async def send_dispute_escalated_to_admin_email(
    to_email: str, admin_name: str, job_id: str, job_title: str,
    homeowner_name: str, tradie_business_name: str, rejection_count: int,
) -> bool:
    """
    Sent to admin when homeowner rejects the tradie\'s resolution claim for the
    2nd time — signals that peer-to-peer resolution has failed and admin must step in.
    """
    name = _first(admin_name)
    url  = f"{APP_BASE_URL}/admin"
    headline = f"Dispute escalated — {rejection_count} homeowner rejection(s)"
    accent   = "#A33030"
    summary  = (
        f"The homeowner <strong>{homeowner_name}</strong> has rejected the tradie "
        f"(<strong>{tradie_business_name}</strong>) claim that the dispute on "
        f"<strong>\"{job_title}\"</strong> is resolved. "
        f"This is rejection #{rejection_count}. Admin action is needed."
    )
    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">{headline}</h1>
      <p style="margin:0 0 18px;font-size:14.5px;line-height:1.7;color:#4A4A48;">G\'day {name},</p>
      {_box(summary, accent, "#FFF5F5")}
      <p style="margin:16px 0;font-size:14px;line-height:1.6;color:#4A4A48;">
        Job ID: <code>{job_id}</code><br>
        Please review the conversation thread and use the Admin Disputes tab to resolve this.
      </p>
      {_btn("Open Admin Panel", url, accent)}"""
    text = (
        f"G\'day {name},\n\n"
        f"Dispute escalation — rejection #{rejection_count}\n\n"
        f"Job: \"{job_title}\" (ID: {job_id})\n"
        f"Homeowner: {homeowner_name}\n"
        f"Tradie: {tradie_business_name}\n\n"
        f"The homeowner has rejected the tradie\'s resolution claim {rejection_count} time(s).\n"
        f"Admin action needed: {url}\n\n"
        f"-- {APP_NAME} system"
    )
    return await _send_raw_email(
        to_email, f"[Admin] Dispute escalated — {job_title}", _base_html(body, accent), text,
    )

