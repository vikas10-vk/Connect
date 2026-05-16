"""
backend/services/resend_service.py

UPDATED — four new email functions added at the bottom:
  send_cert_expiry_reminder_email    Tiered reminder: 30/14/7/1 days before cert expiry
  send_cert_expired_email            Cert has expired — bookings paused for that category
  send_insurance_expiry_reminder_email  Tiered reminder for insurance expiry
  send_insurance_expired_email          Insurance expired — ENTIRE business paused

All existing functions are preserved exactly as written.
"""

import os
import logging
from datetime import date
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True,
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


async def send_tradie_rejected_email(to_email: str, full_name: str, business_name: str, notes: Optional[str] = None) -> bool:
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


async def send_tradie_needs_documents_email(to_email: str, full_name: str, business_name: str, notes: Optional[str] = None) -> bool:
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


async def send_tradie_suspended_email(to_email: str, full_name: str, business_name: str, reason: Optional[str] = None) -> bool:
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
          "new leads for <strong>{category_name}</strong> jobs until a valid licence is verified.<br><br>"
          "✅ <strong>How to get back online</strong><br>"
          "1. Renew your licence with the relevant state authority<br>"
          "2. Submit your new licence number via the dashboard<br>"
          "3. Our team will verify and re-activate your account within 1 business day".format(category_name=category_name),
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
          f"📋 Policy expiry: <strong>{expiry_str}</strong><br>"
          f"⏱ Days remaining: <strong>{days_remaining}</strong><br><br>"
          f"⚠️ {consequence}",
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
        f"— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"{subject_prefix}: your {insurance_label} expires {urgency_word} — {APP_NAME}",
        _base_html(body, accent),
        text,
    )


# ── Insurance expired (day 0) ─────────────────────────────────────────────────

async def send_insurance_expired_email(
    to_email: str,
    full_name: str,
    business_name: str,
    insurance_label: str,
) -> bool:
    """
    Sent when insurance reaches expiry and the business is auto-disabled.
    Every worker in the business has been set to can_accept_jobs=False.
    Clear, direct, tells them exactly what to do to get back online.
    """
    name = _first(full_name)
    url  = f"{APP_BASE_URL}/tradie/dashboard"

    body = f"""
      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;font-weight:500;color:#1A1A1A;">
        Your {insurance_label} has expired — business paused
      </h1>
      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
        G'day {name}, the <strong>{insurance_label}</strong> registered to
        <strong>{business_name}</strong> expired today.
      </p>
      {_box(
          "🔴 <strong>What this means</strong><br>"
          "Your entire business has been paused. <strong>All workers have stopped receiving job assignments</strong> "
          "until a valid insurance policy is verified.<br><br>"
          "✅ <strong>How to get back online</strong><br>"
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
        f"Your entire business has been paused — all workers have stopped receiving job assignments.\n\n"
        f"To get back online:\n"
        f"1. Renew your policy with your insurer\n"
        f"2. Submit the new policy number at: {url}\n"
        f"3. Our team will verify within 1 business day\n\n"
        f"If this is an error, reply to this email immediately.\n\n"
        f"— The {APP_NAME} team"
    )
    return await _send_raw_email(
        to_email,
        f"Your {insurance_label} has expired — {business_name} paused on {APP_NAME}",
        _base_html(body, "#A33030"),
        text,
    )
