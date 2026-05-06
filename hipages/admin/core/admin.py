"""
admin/core/admin.py

ProConnect Ops Dashboard — built on Django admin.

Panels (original):
  ⏳ Pending Verification Queue  — tradies waiting for approval
  ⭐ Review Moderation Queue     — reviews waiting to go public
  💼 All Jobs                   — filterable by status, searchable
  👤 Users                      — homeowners + tradies
  🔍 Audit Log                  — every mutating API request
  📋 Job Events                 — state machine trail per job
  + supporting: Leads, Categories, All Tradies, All Reviews

NEW panels:
  📜 Certification Queue        — trade licence numbers awaiting admin verification
                                   Includes state registry pre-filled links.
                                   Approve / reject with structured reason codes.
                                   Auto-activates workers when gate conditions met.
  🛡️  Insurance Queue           — insurance policies awaiting admin verification
                                   Approve / reject with structured reason codes.
                                   Approval disables entire business on expiry.
  👥 Team Members               — read-only worker overview per business
                                   Shows can_accept_jobs gate status, selfie status.

Design rules:
  - Most models are read-only (managed=False, FastAPI owns writes)
  - verified_by is LEFT NULL for admin approvals (it's a FK to FastAPI user UUIDs).
    Django admin LogEntry is the audit trail for who approved what.
  - verified_at IS written (timezone.now()) on every approval/rejection.
  - Approval actions check activation gate: cert + insurance both verified
    → can_accept_jobs flipped to True directly via ORM (same DB, instant effect).
  - Never show passwords, tokens, or raw lat/lng to ops staff.
"""
import datetime

from django.contrib import admin
from django.utils.html import mark_safe, format_html
from django.utils import timezone
from django.db.models import Count, Q

from .models import (
    User, TradieProfile, PendingVerification,
    Category, Job, Lead,
    Review, PendingReview,
    AuditEvent, JobEvent,
    # ── new models (merged from models_additions.py) ──
    TradieCertification, PendingCertification,
    InsurancePolicy, PendingInsurance,
    TeamMember,
)

# ── Admin site customisation ──────────────────────────────────────────────────

admin.site.site_header  = "ProConnect Ops"
admin.site.site_title   = "ProConnect Admin"
admin.site.index_title  = "Platform Control Room"


# ── Colour helpers ────────────────────────────────────────────────────────────

STATUS_COLOURS = {
    # Job statuses
    "open":              ("#C5563A", "#F5EDE9"),
    "quoted":            ("#B85C00", "#FFF3E0"),
    "hired":             ("#5B3FA6", "#EEE8FF"),
    "in_progress":       ("#0077AA", "#E0F4FF"),
    "completed":         ("#2E7D5A", "#E8F5EE"),
    "cancelled":         ("#A33030", "#FFEBEB"),
    "closed":            ("#7A6558", "#F0EDE8"),
    # Review statuses
    "pending":           ("#B85C00", "#FFF3E0"),
    "approved":          ("#2E7D5A", "#E8F5EE"),
    "rejected":          ("#A33030", "#FFEBEB"),
    # Verification statuses
    "pending_review":    ("#B85C00", "#FFF3E0"),
    "needs_documents":   ("#0077AA", "#E0F4FF"),
    "suspended":         ("#A33030", "#FFEBEB"),
    # Cert / insurance statuses
    "in_review":         ("#5B3FA6", "#EEE8FF"),
    "verified":          ("#2E7D5A", "#E8F5EE"),
    "expired":           ("#A33030", "#FFEBEB"),
    # Lead statuses
    "new":               ("#0077AA", "#E0F4FF"),
    "viewed":            ("#5B3FA6", "#EEE8FF"),
    "quoted_lead":       ("#2E7D5A", "#E8F5EE"),
    "declined":          ("#A33030", "#FFEBEB"),
    # HTTP methods
    "POST":              ("#2E7D5A", "#E8F5EE"),
    "PATCH":             ("#B85C00", "#FFF3E0"),
    "PUT":               ("#0077AA", "#E0F4FF"),
    "DELETE":            ("#A33030", "#FFEBEB"),
}


def status_badge(value: str, label: str | None = None) -> str:
    color, bg = STATUS_COLOURS.get(value, ("#7A6558", "#F0EDE8"))
    return mark_safe(
        f'<span style="padding:3px 9px;border-radius:10px;background:{bg};'
        f'color:{color};font-size:11px;font-weight:700;white-space:nowrap">'
        f'{label or value}</span>'
    )


def star_rating(rating: int) -> str:
    stars = "★" * rating + "☆" * (5 - rating)
    color = "#F59E0B" if rating >= 4 else "#B85C00" if rating >= 3 else "#A33030"
    return mark_safe(
        f'<span style="color:{color};font-size:13px;letter-spacing:1px">'
        f'{stars}</span> '
        f'<span style="font-size:11px;color:#7A6558">({rating}/5)</span>'
    )


# ── State registry URLs ───────────────────────────────────────────────────────
# Pre-filled where the registry supports URL query params.
# For the rest, admin copies the licence number from the detail panel and
# pastes it into the registry search page.

STATE_REGISTRY = {
    "VIC": {
        "name": "VBA (Victoria)",
        "url":  "https://www.vba.vic.gov.au/tools/check-a-licence?q={licence}",
        "note": "Licence number pre-filled. Click Search on the VBA page.",
    },
    "NSW": {
        "name": "NSW Fair Trading",
        "url":  "https://www.onlineservices.fairtrading.nsw.gov.au/RLSearch.aspx",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "QLD": {
        "name": "QBCC (Queensland)",
        "url":  "https://www.qbcc.qld.gov.au/licence-search",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "WA": {
        "name": "WA Building Commission",
        "url":  "https://www.bsc.wa.gov.au/search-contractors.aspx",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "SA": {
        "name": "SA CBS",
        "url":  "https://www.sa.gov.au/topics/housing/building-and-renovation/licensing-search",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "TAS": {
        "name": "TAS CBOS",
        "url":  "https://www.cbos.tas.gov.au/topics/licensing/search",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "NT": {
        "name": "NT Government",
        "url":  "https://nt.gov.au/industry/licences-and-permits",
        "note": "Copy the licence number above and paste it into the search field.",
    },
    "ACT": {
        "name": "Access Canberra",
        "url":  "https://www.accesscanberra.act.gov.au/s/article/construction-licences",
        "note": "Copy the licence number above and paste it into the search field.",
    },
}


def registry_link_html(licence_number: str, issuing_state: str) -> str:
    """
    Returns a formatted HTML block with:
      - The licence number in a copyable code block
      - A button linking to the state registry (pre-filled where possible)
      - A short instruction note
    """
    reg = STATE_REGISTRY.get(issuing_state.upper())
    if not reg:
        return mark_safe(
            f'<code style="font-size:13px;background:#F4EEDD;padding:4px 8px;'
            f'border-radius:6px">{licence_number}</code>'
        )
    url  = reg["url"].format(licence=licence_number)
    name = reg["name"]
    note = reg["note"]
    return mark_safe(
        f'<div style="margin:4px 0">'
        f'  <code style="font-size:14px;font-weight:700;background:#F4EEDD;'
        f'         padding:5px 10px;border-radius:6px;letter-spacing:0.05em">'
        f'    {licence_number}'
        f'  </code>'
        f'  &nbsp;&nbsp;'
        f'  <a href="{url}" target="_blank" rel="noopener" '
        f'     style="display:inline-block;padding:5px 14px;background:#2E7D5A;'
        f'            color:#fff;border-radius:7px;font-size:12px;font-weight:700;'
        f'            text-decoration:none">'
        f'    🔍 Search {name}'
        f'  </a>'
        f'  <br>'
        f'  <span style="font-size:11.5px;color:#7A6558;margin-top:3px;display:block">'
        f'    {note}'
        f'  </span>'
        f'</div>'
    )


def photo_preview_html(url: str | None, label: str = "View Document") -> str:
    if not url:
        return mark_safe(
            '<span style="color:#A89080;font-size:12px;font-style:italic">No photo uploaded</span>'
        )
    return mark_safe(
        f'<a href="{url}" target="_blank" rel="noopener" '
        f'   style="display:inline-block;padding:5px 14px;background:#0077AA;'
        f'          color:#fff;border-radius:7px;font-size:12px;font-weight:700;'
        f'          text-decoration:none">'
        f'  📄 {label}'
        f'</a>'
    )


def coverage_display(cents: int) -> str:
    return f"${cents / 100:,.0f}"


# ── Activation gate helpers ────────────────────────────────────────────────────

def _maybe_activate_worker_from_cert(cert: TradieCertification) -> str:
    """
    After a cert is verified, check if the associated tradie / worker now
    meets all gate conditions. If so, flip can_accept_jobs = True.

    Returns a human-readable string describing what happened (for admin message).

    GATE for SOLO TRADIE / OWNER:
      - At least one verified, non-expired cert on the profile
      - At least one verified, non-expired public liability insurance on the profile
      → flip owner TeamMember.can_accept_jobs = True
        and set TradieProfile.is_available = True

    GATE for WORKER:
      - At least one verified, non-expired cert on the worker
      → flip TeamMember.can_accept_jobs = True
        (worker inherits business insurance from the profile level)
    """
    today = datetime.date.today()

    if cert.team_member_id:
        has_cert = TradieCertification.objects.filter(
            team_member_id=cert.team_member_id,
            status='verified',
            expires_at__gt=today,
        ).exists()
        if has_cert:
            updated = TeamMember.objects.filter(id=cert.team_member_id).update(can_accept_jobs=True)
            if updated:
                return f"Worker {cert.team_member_id[:8]}… activated (can_accept_jobs → True)."
        return ""

    elif cert.tradie_profile_id:
        has_cert = TradieCertification.objects.filter(
            tradie_profile_id=cert.tradie_profile_id,
            status='verified',
            expires_at__gt=today,
        ).exists()
        has_insurance = InsurancePolicy.objects.filter(
            tradie_profile_id=cert.tradie_profile_id,
            insurance_type='public_liability',
            status='verified',
            expires_at__gt=today,
        ).exists()
        if has_cert and has_insurance:
            TeamMember.objects.filter(
                business_id=cert.tradie_profile_id,
                role='owner',
            ).update(can_accept_jobs=True)
            TradieProfile.objects.filter(id=cert.tradie_profile_id).update(is_available=True)
            return f"Business {cert.tradie_profile_id[:8]}… owner activated."
        elif has_cert and not has_insurance:
            return "Cert verified ✓. Awaiting public liability insurance verification before activation."
    return ""


def _maybe_activate_business_from_insurance(policy: InsurancePolicy) -> str:
    """
    After an insurance policy is verified, check if the business now meets
    the activation gate. If so, flip owner can_accept_jobs = True.
    Same gate as above but triggered from the insurance side.
    """
    today = datetime.date.today()
    has_cert = TradieCertification.objects.filter(
        tradie_profile_id=policy.tradie_profile_id,
        status='verified',
        expires_at__gt=today,
    ).exists()
    if policy.insurance_type == 'public_liability' and has_cert:
        TeamMember.objects.filter(
            business_id=policy.tradie_profile_id,
            role='owner',
        ).update(can_accept_jobs=True)
        TradieProfile.objects.filter(id=policy.tradie_profile_id).update(is_available=True)
        return f"Business {policy.tradie_profile_id[:8]}… activated — cert + insurance both verified."
    elif policy.insurance_type == 'public_liability' and not has_cert:
        return "Insurance verified ✓. Awaiting trade licence verification before activation."
    return ""


# ── Read-only mixin ───────────────────────────────────────────────────────────

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING INLINES — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

class JobEventInline(admin.TabularInline):
    model       = JobEvent
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ('created_at', 'actor_role', 'action', 'old_status', 'new_status', 'note', 'ip_address')
    readonly_fields = ('created_at', 'actor_role', 'action', 'old_status', 'new_status', 'note', 'ip_address')
    ordering    = ('created_at',)

    def old_status(self, obj):
        val = (obj.old_value or {}).get("status", "—")
        return status_badge(val) if val != "—" else "—"
    old_status.short_description = "From"

    def new_status(self, obj):
        val = (obj.new_value or {}).get("status", "—")
        return status_badge(val) if val != "—" else "—"
    new_status.short_description = "To"

    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class LeadInline(admin.TabularInline):
    model       = Lead
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ('tradie', 'status_badge_col', 'credits_charged', 'sent_at')
    readonly_fields = ('tradie', 'status_badge_col', 'credits_charged', 'sent_at')

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = "Status"

    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════════
# NEW INLINES
# ═══════════════════════════════════════════════════════════════════════════

class CertificationInline(admin.TabularInline):
    """
    Shows a tradie's certification submissions inline on their profile detail page.
    Read-only — approval happens in the Certification Queue panel.
    """
    model       = TradieCertification
    fk_name     = 'tradie_profile'
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ('category', 'licence_number', 'issuing_state', 'holder_name',
                   'expires_at', 'status_col', 'registry_col', 'photo_col')
    readonly_fields = ('category', 'licence_number', 'issuing_state', 'holder_name',
                       'expires_at', 'status_col', 'registry_col', 'photo_col')

    def status_col(self, obj):
        return status_badge(obj.status)
    status_col.short_description = 'Status'

    def registry_col(self, obj):
        return registry_link_html(obj.licence_number, obj.issuing_state)
    registry_col.short_description = 'Registry Lookup'

    def photo_col(self, obj):
        return photo_preview_html(obj.photo_url, "View Card Photo")
    photo_col.short_description = 'Photo'

    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class InsurancePolicyInline(admin.TabularInline):
    """
    Shows a tradie's insurance submissions inline on their profile detail page.
    """
    model       = InsurancePolicy
    fk_name     = 'tradie_profile'
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ('insurance_type', 'insurer_name', 'policy_number',
                   'coverage_col', 'expires_at', 'status_col', 'document_col')
    readonly_fields = ('insurance_type', 'insurer_name', 'policy_number',
                       'coverage_col', 'expires_at', 'status_col', 'document_col')

    def status_col(self, obj):
        return status_badge(obj.status)
    status_col.short_description = 'Status'

    def coverage_col(self, obj):
        return coverage_display(obj.coverage_amount_cents)
    coverage_col.short_description = 'Coverage'

    def document_col(self, obj):
        return photo_preview_html(obj.document_url, "View Certificate")
    document_col.short_description = 'Document'

    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class TeamMemberInline(admin.TabularInline):
    """
    Shows workers in a business inline on the tradie profile detail page.
    """
    model       = TeamMember
    fk_name     = 'business'
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ('full_name', 'email', 'role_col', 'is_active',
                   'can_accept_jobs', 'jobs_completed', 'selfie_col')
    readonly_fields = ('full_name', 'email', 'role_col', 'is_active',
                       'can_accept_jobs', 'jobs_completed', 'selfie_col')

    def role_col(self, obj):
        color = "#C5563A" if obj.role == 'owner' else "#5B3FA6"
        bg    = "#F5EDE9" if obj.role == 'owner' else "#EEE8FF"
        return mark_safe(
            f'<span style="padding:2px 8px;border-radius:8px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">{obj.role}</span>'
        )
    role_col.short_description = 'Role'

    def selfie_col(self, obj):
        if obj.selfie_url:
            return mark_safe(
                f'<a href="{obj.selfie_url}" target="_blank" '
                f'   style="color:#2E7D5A;font-size:11px;font-weight:700">📷 View</a>'
            )
        return mark_safe('<span style="color:#A89080;font-size:11px">No selfie</span>')
    selfie_col.short_description = 'Selfie'

    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING ADMIN CLASSES — PRESERVED EXACTLY
# (TradieProfileAdmin updated to add inlines)
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(User)
class UserAdmin(ReadOnlyAdmin):
    list_display        = ('full_name', 'email', 'role_badge', 'is_active', 'is_verified', 'created_at')
    list_filter         = ('role', 'is_active', 'is_verified')
    search_fields       = ('email', 'full_name', 'phone')
    readonly_fields     = ('id', 'email', 'full_name', 'phone', 'role', 'is_active', 'is_verified', 'created_at')
    list_select_related = False
    date_hierarchy      = 'created_at'
    ordering            = ('-created_at',)

    def role_badge(self, obj):
        colors = {
            'homeowner': ('#0077AA', '#E0F4FF'),
            'tradie':    ('#5B3FA6', '#EEE8FF'),
            'admin':     ('#C5563A', '#F5EDE9'),
        }
        color, bg = colors.get(obj.role, ("#7A6558", "#F0EDE8"))
        return mark_safe(
            f'<span style="padding:3px 9px;border-radius:10px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">{obj.role}</span>'
        )
    role_badge.short_description = 'Role'


@admin.register(TradieProfile)
class TradieProfileAdmin(ReadOnlyAdmin):
    list_display    = ('business_name', 'user_email', 'suburb', 'state',
                       'verif_badge', 'is_available', 'credits',
                       'cert_gate_col', 'insurance_gate_col', 'created_at')
    list_filter     = ('verification_status', 'is_available', 'solo_or_team', 'state')
    search_fields   = ('business_name', 'abn', 'user__email', 'user__full_name')
    readonly_fields = ('id', 'user', 'business_name', 'abn', 'suburb', 'state',
                       'credits', 'is_available', 'avatar_url', 'logo_url',
                       'verification_status', 'verification_notes',
                       'reviewed_at', 'reviewed_by',
                       'solo_or_team', 'team_size',
                       'rating_avg', 'rating_count',
                       'verified_at', 'created_at',
                       'cert_gate_col', 'insurance_gate_col')
    list_select_related = ('user',)
    date_hierarchy      = 'created_at'
    # NEW: show cert, insurance, and team member inlines on the detail view
    inlines             = [CertificationInline, InsurancePolicyInline, TeamMemberInline]

    def user_email(self, obj):
        try:
            return obj.user.email
        except Exception:
            return "—"
    user_email.short_description = 'Email'

    def verif_badge(self, obj):
        return status_badge(obj.verification_status)
    verif_badge.short_description = 'Verification'

    def cert_gate_col(self, obj):
        today = datetime.date.today()
        has = TradieCertification.objects.filter(
            tradie_profile=obj,
            status='verified',
            expires_at__gt=today,
        ).exists()
        return mark_safe(
            '<span style="color:#2E7D5A;font-weight:700">✓ Cert</span>'
            if has else
            '<span style="color:#A89080;font-size:11px">No cert</span>'
        )
    cert_gate_col.short_description = 'Cert'

    def insurance_gate_col(self, obj):
        today = datetime.date.today()
        has = InsurancePolicy.objects.filter(
            tradie_profile=obj,
            insurance_type='public_liability',
            status='verified',
            expires_at__gt=today,
        ).exists()
        return mark_safe(
            '<span style="color:#2E7D5A;font-weight:700">✓ Insured</span>'
            if has else
            '<span style="color:#A89080;font-size:11px">No insurance</span>'
        )
    insurance_gate_col.short_description = 'Insurance'


@admin.register(PendingVerification)
class PendingVerificationAdmin(admin.ModelAdmin):
    list_display    = ('business_name', 'user_email', 'abn', 'suburb', 'state',
                       'solo_or_team', 'verif_badge', 'days_waiting',
                       'cert_gate_col', 'insurance_gate_col', 'created_at')
    list_filter     = ('verification_status', 'state', 'solo_or_team')
    search_fields   = ('business_name', 'abn', 'user__email')
    ordering        = ('created_at',)
    actions         = ['approve_tradies', 'reject_tradies', 'request_documents', 'suspend_tradies']
    readonly_fields = ('id', 'user', 'business_name', 'abn', 'suburb', 'state',
                       'credits', 'is_available', 'avatar_url',
                       'solo_or_team', 'team_size', 'created_at')
    inlines         = [CertificationInline, InsurancePolicyInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            verification_status__in=['pending_review', 'needs_documents']
        )

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    def user_email(self, obj):
        try:
            return obj.user.email
        except Exception:
            return "—"
    user_email.short_description = 'Email'

    def verif_badge(self, obj):
        return status_badge(obj.verification_status)
    verif_badge.short_description = 'Status'

    def days_waiting(self, obj):
        if not obj.created_at:
            return "—"
        delta = (timezone.now() - obj.created_at).days
        color = "#A33030" if delta > 3 else "#B85C00" if delta > 1 else "#2E7D5A"
        return mark_safe(f'<span style="color:{color};font-weight:700">{delta}d</span>')
    days_waiting.short_description = 'Waiting'

    def cert_gate_col(self, obj):
        today = datetime.date.today()
        has = TradieCertification.objects.filter(
            tradie_profile=obj, status='verified', expires_at__gt=today,
        ).exists()
        return mark_safe(
            '<span style="color:#2E7D5A;font-weight:700">✓</span>'
            if has else
            '<span style="color:#B85C00">⏳</span>'
        )
    cert_gate_col.short_description = 'Cert'

    def insurance_gate_col(self, obj):
        today = datetime.date.today()
        has = InsurancePolicy.objects.filter(
            tradie_profile=obj, insurance_type='public_liability',
            status='verified', expires_at__gt=today,
        ).exists()
        return mark_safe(
            '<span style="color:#2E7D5A;font-weight:700">✓</span>'
            if has else
            '<span style="color:#B85C00">⏳</span>'
        )
    insurance_gate_col.short_description = 'Insurance'

    @admin.action(description="✅ Approve selected tradies")
    def approve_tradies(self, request, queryset):
        updated = queryset.update(
            verification_status='approved',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} tradie(s) approved.")

    @admin.action(description="❌ Reject selected tradies")
    def reject_tradies(self, request, queryset):
        updated = queryset.update(
            verification_status='rejected',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} tradie(s) rejected.")

    @admin.action(description="📄 Request more documents")
    def request_documents(self, request, queryset):
        updated = queryset.update(
            verification_status='needs_documents',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} tradie(s) flagged for more documents.")

    @admin.action(description="🚫 Suspend selected tradies")
    def suspend_tradies(self, request, queryset):
        updated = queryset.update(
            verification_status='suspended',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} tradie(s) suspended.")


@admin.register(Job)
class JobAdmin(ReadOnlyAdmin):
    list_display    = ('title', 'homeowner_email', 'category', 'suburb', 'state',
                       'status_badge_col', 'budget_range', 'lead_task_short', 'is_deleted', 'created_at')
    list_filter     = ('status', 'is_deleted', 'state', 'urgency')
    search_fields   = ('title', 'homeowner__email', 'homeowner__full_name', 'suburb')
    readonly_fields = ('id', 'homeowner', 'category', 'title', 'description',
                       'suburb', 'state', 'status', 'urgency',
                       'budget_min', 'budget_max',
                       'is_deleted', 'completed_at', 'created_at', 'updated_at')
    list_select_related = ('homeowner', 'category')
    date_hierarchy  = 'created_at'
    inlines         = [JobEventInline, LeadInline]

    def lead_task_short(self, obj):
        if not obj.lead_task_id:
            return mark_safe('<span style="color:#A89080;font-size:11px">No task</span>')
        return mark_safe(f'<code style="font-size:10px">{obj.lead_task_id[:8]}…</code>')
    lead_task_short.short_description = 'Celery Task'

    def homeowner_email(self, obj):
        try:
            return obj.homeowner.email
        except Exception:
            return "—"
    homeowner_email.short_description = 'Homeowner'

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = 'Status'

    def budget_range(self, obj):
        if obj.budget_min or obj.budget_max:
            lo = f"${int(obj.budget_min):,}" if obj.budget_min else "?"
            hi = f"${int(obj.budget_max):,}" if obj.budget_max else "?"
            return f"{lo} – {hi}"
        return "—"
    budget_range.short_description = 'Budget'


@admin.register(Lead)
class LeadAdmin(ReadOnlyAdmin):
    list_display    = ('id_short', 'job', 'tradie', 'status_badge_col', 'credits_charged', 'sent_at')
    list_filter     = ('status',)
    search_fields   = ('job__title', 'tradie__business_name')
    readonly_fields = ('id', 'job', 'tradie', 'credits_charged', 'status', 'sent_at')
    list_select_related = ('job', 'tradie')
    date_hierarchy  = 'sent_at'

    def id_short(self, obj):
        return obj.id[:8] + "…"
    id_short.short_description = 'ID'

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = 'Status'


@admin.register(Review)
class ReviewAdmin(ReadOnlyAdmin):
    list_display    = ('rating_stars', 'tradie', 'job', 'status_badge_col',
                       'comment_preview', 'created_at')
    list_filter     = ('status', 'rating')
    search_fields   = ('job__title', 'tradie__business_name', 'homeowner__email', 'comment')
    readonly_fields = ('id', 'job', 'homeowner', 'tradie', 'rating',
                       'comment', 'status', 'reviewed_at', 'reviewed_by', 'created_at')
    list_select_related = ('job', 'tradie', 'homeowner')
    date_hierarchy  = 'created_at'

    def rating_stars(self, obj):
        return star_rating(obj.rating)
    rating_stars.short_description = 'Rating'

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = 'Status'

    def comment_preview(self, obj):
        if not obj.comment:
            return mark_safe('<span style="color:#A89080;font-style:italic">No comment</span>')
        preview = obj.comment[:80] + ("…" if len(obj.comment) > 80 else "")
        return preview
    comment_preview.short_description = 'Comment'


@admin.register(PendingReview)
class PendingReviewAdmin(admin.ModelAdmin):
    list_display    = ('rating_stars', 'tradie', 'homeowner_name', 'job',
                       'status_badge_col', 'comment_preview', 'created_at')
    list_filter     = ('rating',)
    search_fields   = ('job__title', 'tradie__business_name', 'homeowner__email', 'comment')
    ordering        = ('created_at',)
    actions         = ['approve_reviews', 'reject_reviews']
    readonly_fields = ('id', 'job', 'homeowner', 'tradie', 'rating',
                       'comment', 'created_at')
    list_select_related = ('job', 'tradie', 'homeowner')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(status='pending')

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    def rating_stars(self, obj):
        return star_rating(obj.rating)
    rating_stars.short_description = 'Rating'

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = 'Status'

    def homeowner_name(self, obj):
        try:
            return obj.homeowner.full_name
        except Exception:
            return "—"
    homeowner_name.short_description = 'Homeowner'

    def comment_preview(self, obj):
        if not obj.comment:
            return mark_safe('<span style="color:#A89080;font-style:italic">No comment</span>')
        return (obj.comment[:100] + "…") if len(obj.comment) > 100 else obj.comment
    comment_preview.short_description = 'Comment'

    @admin.action(description="✅ Approve selected reviews (make public)")
    def approve_reviews(self, request, queryset):
        updated = queryset.update(status='approved', reviewed_at=timezone.now())
        self.message_user(request, f"{updated} review(s) approved and now public.")

    @admin.action(description="❌ Reject selected reviews (keep hidden)")
    def reject_reviews(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, f"{updated} review(s) rejected.")


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAdmin):
    list_display    = ('created_at', 'method_badge', 'path_display', 'entity_type',
                       'actor_role_badge', 'status_code_display', 'ip_address')
    list_filter     = ('action', 'entity_type', 'actor_role', 'status_code')
    search_fields   = ('path', 'actor_id', 'entity_id', 'ip_address')
    readonly_fields = ('id', 'entity_type', 'entity_id', 'actor_id', 'actor_role',
                       'action', 'path', 'status_code', 'ip_address', 'user_agent', 'created_at')
    date_hierarchy  = 'created_at'
    ordering        = ('-created_at',)

    def method_badge(self, obj):
        return status_badge(obj.action)
    method_badge.short_description = 'Method'

    def path_display(self, obj):
        short = obj.path[:60] + ("…" if len(obj.path) > 60 else "")
        return mark_safe(f'<code style="font-size:11px">{short}</code>')
    path_display.short_description = 'Path'

    def actor_role_badge(self, obj):
        if not obj.actor_role:
            return "—"
        colors = {
            'homeowner': ('#0077AA', '#E0F4FF'),
            'tradie':    ('#5B3FA6', '#EEE8FF'),
            'admin':     ('#C5563A', '#F5EDE9'),
            'anonymous': ('#7A6558', '#F0EDE8'),
        }
        color, bg = colors.get(obj.actor_role, ("#7A6558", "#F0EDE8"))
        return mark_safe(
            f'<span style="padding:3px 9px;border-radius:10px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">{obj.actor_role}</span>'
        )
    actor_role_badge.short_description = 'Role'

    def status_code_display(self, obj):
        if not obj.status_code:
            return "—"
        color = "#2E7D5A" if obj.status_code < 300 else "#A33030"
        return mark_safe(f'<span style="color:{color};font-weight:700">{obj.status_code}</span>')
    status_code_display.short_description = 'HTTP'


@admin.register(JobEvent)
class JobEventAdmin(ReadOnlyAdmin):
    list_display    = ('created_at', 'job', 'actor_role', 'action',
                       'old_status', 'arrow', 'new_status', 'note')
    list_filter     = ('action', 'actor_role')
    search_fields   = ('job__title', 'actor_id', 'note')
    readonly_fields = ('id', 'job', 'actor_id', 'actor_role', 'action',
                       'old_value', 'new_value', 'note', 'ip_address', 'created_at')
    list_select_related = ('job',)
    date_hierarchy  = 'created_at'
    ordering        = ('-created_at',)

    def old_status(self, obj):
        val = (obj.old_value or {}).get("status", "—")
        return status_badge(val) if val != "—" else "—"
    old_status.short_description = 'From'

    def new_status(self, obj):
        val = (obj.new_value or {}).get("status", "—")
        return status_badge(val) if val != "—" else "—"
    new_status.short_description = 'To'

    def arrow(self, obj):
        return mark_safe('<span style="color:#A89080;font-size:14px">→</span>')
    arrow.short_description = ''


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin):
    list_display  = ('name', 'slug', 'level_badge', 'is_active')
    list_filter   = ('level', 'is_active')
    search_fields = ('name', 'slug')
    ordering      = ('level', 'name')

    def level_badge(self, obj):
        labels = {1: 'Trade', 2: 'Subcategory', 3: 'Task'}
        colors = {1: ('#C5563A', '#F5EDE9'), 2: ('#5B3FA6', '#EEE8FF'), 3: ('#7A6558', '#F0EDE8')}
        label = labels.get(obj.level, str(obj.level))
        color, bg = colors.get(obj.level, ("#7A6558", "#F0EDE8"))
        return mark_safe(
            f'<span style="padding:2px 8px;border-radius:8px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">L{obj.level} {label}</span>'
        )
    level_badge.short_description = 'Level'


# ═══════════════════════════════════════════════════════════════════════════
# NEW: CERTIFICATION VERIFICATION QUEUE
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(PendingCertification)
class PendingCertificationAdmin(admin.ModelAdmin):
    """
    The certification verification workflow screen.

    WORKFLOW FOR OPS TEAM:
      1. Open the detail view for a pending cert.
      2. Find the "Registry Lookup" row — click "Search [State Registry]".
         The licence number is displayed prominently for copy-paste.
      3. Verify the number exists, matches the holder name, and covers the
         correct trade category.
      4. Return to the cert detail. Click ✅ Approve or choose a rejection action.
         Approval instantly activates the tradie / worker if all gates are met.

    BULK ACTIONS (list view):
      ✅ Approve certifications
      ❌ Reject — Invalid number
      ❌ Reject — Expired
      ❌ Reject — Name mismatch
      ❌ Reject — Cannot verify

    STRUCTURED REJECTION:
      Every rejection writes a structured reason code so the tradie receives a
      specific email ("Your licence number could not be verified — it appears
      to be expired") rather than a generic rejection notice.
    """
    list_display    = ('licence_number_col', 'issuing_state', 'holder_name',
                       'category', 'owner_col', 'status_col',
                       'photo_col', 'days_waiting', 'expires_at', 'created_at')
    list_filter     = ('status', 'issuing_state', 'category')
    search_fields   = ('licence_number', 'holder_name',
                       'tradie_profile__business_name',
                       'tradie_profile__abn')
    ordering        = ('created_at',)   # oldest first — FIFO queue
    actions         = [
        'approve_certifications',
        'reject_invalid_number',
        'reject_expired',
        'reject_name_mismatch',
        'reject_cannot_verify',
    ]
    readonly_fields = (
        'id', 'tradie_profile', 'team_member_id', 'category',
        'holder_name', 'issued_at', 'expires_at',
        'verified_at', 'created_at', 'updated_at',
        # rendered helpers
        'registry_lookup_panel', 'photo_preview_panel',
        'reminder_30d_sent_at', 'reminder_14d_sent_at',
        'reminder_7d_sent_at',  'reminder_1d_sent_at',
    )
    fields = (
        # ── Identity ─────────────────────────────────────────────
        'tradie_profile', 'team_member_id', 'category',
        # ── Licence details ───────────────────────────────────────
        'registry_lookup_panel',    # prominent rendered block
        'photo_preview_panel',
        'issuing_body', 'holder_name', 'issued_at', 'expires_at',
        # ── Admin decision ────────────────────────────────────────
        'status', 'rejection_reason', 'rejection_note',
        # ── Timestamps ───────────────────────────────────────────
        'verified_at', 'created_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            status__in=['pending', 'in_review']
        ).select_related('category', 'tradie_profile')

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    # ── List columns ─────────────────────────────────────────────

    def licence_number_col(self, obj):
        return mark_safe(
            f'<code style="font-size:12px;font-weight:700;background:#F4EEDD;'
            f'padding:3px 8px;border-radius:6px">{obj.licence_number}</code>'
        )
    licence_number_col.short_description = 'Licence #'

    def status_col(self, obj):
        return status_badge(obj.status)
    status_col.short_description = 'Status'

    def owner_col(self, obj):
        if obj.tradie_profile:
            return obj.tradie_profile.business_name
        return mark_safe(
            f'<span style="color:#7A6558;font-size:11px">Worker {(obj.team_member_id or "")[:8]}…</span>'
        )
    owner_col.short_description = 'Business / Worker'

    def photo_col(self, obj):
        if obj.photo_url:
            return mark_safe('<span style="color:#2E7D5A;font-weight:700">📷 Yes</span>')
        return mark_safe('<span style="color:#A89080;font-size:11px">None</span>')
    photo_col.short_description = 'Photo'

    def days_waiting(self, obj):
        if not obj.created_at:
            return "—"
        delta = (timezone.now() - obj.created_at).days
        color = "#A33030" if delta > 3 else "#B85C00" if delta > 1 else "#2E7D5A"
        return mark_safe(f'<span style="color:{color};font-weight:700">{delta}d</span>')
    days_waiting.short_description = 'Waiting'

    # ── Detail view rendered panels ───────────────────────────────

    def registry_lookup_panel(self, obj):
        """
        Prominently rendered block in the detail view.
        Shows the licence number + a button to open the state registry.
        Admin clicks, verifies, comes back and approves/rejects.
        """
        return registry_link_html(obj.licence_number, obj.issuing_state)
    registry_lookup_panel.short_description = '🔍 Registry Lookup'

    def photo_preview_panel(self, obj):
        return photo_preview_html(obj.photo_url, "View Licence Card Photo")
    photo_preview_panel.short_description = '📷 Licence Card Photo'

    # ── Bulk actions ──────────────────────────────────────────────

    @admin.action(description="✅ Approve selected certifications")
    def approve_certifications(self, request, queryset):
        now       = timezone.now()
        count     = 0
        activated = []
        for cert in queryset.select_related('tradie_profile'):
            cert.status      = 'verified'
            cert.verified_at = now
            cert.save(update_fields=['status', 'verified_at', 'updated_at'])
            count += 1
            note = _maybe_activate_worker_from_cert(cert)
            if note:
                activated.append(note)
        msg = f"{count} certification(s) approved."
        if activated:
            msg += " " + " | ".join(activated)
        self.message_user(request, msg)

    @admin.action(description="❌ Reject — Invalid number (not found in registry)")
    def reject_invalid_number(self, request, queryset):
        self._bulk_reject(request, queryset, 'invalid_number')

    @admin.action(description="❌ Reject — Expired (licence has lapsed)")
    def reject_expired(self, request, queryset):
        self._bulk_reject(request, queryset, 'expired')

    @admin.action(description="❌ Reject — Name mismatch (holder name doesn't match registry)")
    def reject_name_mismatch(self, request, queryset):
        self._bulk_reject(request, queryset, 'name_mismatch')

    @admin.action(description="❌ Reject — Cannot verify (registry unavailable / photo unclear)")
    def reject_cannot_verify(self, request, queryset):
        self._bulk_reject(request, queryset, 'cannot_verify')

    def _bulk_reject(self, request, queryset, reason: str):
        now     = timezone.now()
        updated = queryset.update(
            status='rejected',
            rejection_reason=reason,
            verified_at=now,
        )
        reason_labels = {
            'invalid_number': 'invalid number',
            'expired':        'expired',
            'name_mismatch':  'name mismatch',
            'cannot_verify':  'cannot verify',
        }
        self.message_user(
            request,
            f"{updated} certification(s) rejected ({reason_labels.get(reason, reason)}). "
            f"Tradie will be notified by the verification email task within 2 minutes.",
        )


# ═══════════════════════════════════════════════════════════════════════════
# NEW: INSURANCE VERIFICATION QUEUE
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(PendingInsurance)
class PendingInsuranceAdmin(admin.ModelAdmin):
    """
    Insurance policy verification workflow screen.

    WORKFLOW FOR OPS TEAM:
      1. Open the detail view for a pending policy.
      2. Note the insurer name, policy number, and holder name.
      3. Call or email the insurer to confirm the policy is valid and current
         (or check the uploaded certificate of currency).
      4. Verify the coverage amount meets the minimum for the trade category
         (currently $20M for most licensed trades in Australia).
      5. Return. Click ✅ Approve or choose a rejection action.
         Approval activates the business if certs are also verified.

    BULK ACTIONS:
      ✅ Approve insurance policies
      ❌ Reject — Invalid policy number
      ❌ Reject — Policy expired
      ❌ Reject — Name mismatch
      ❌ Reject — Insufficient coverage
      ❌ Reject — Cannot verify
    """
    list_display    = ('policy_number_col', 'insurance_type_col', 'insurer_name',
                       'coverage_col', 'holder_name', 'business_name_col',
                       'expires_at', 'status_col', 'document_col',
                       'days_waiting', 'created_at')
    list_filter     = ('status', 'insurance_type')
    search_fields   = ('policy_number', 'insurer_name', 'holder_name',
                       'tradie_profile__business_name')
    ordering        = ('created_at',)
    actions         = [
        'approve_insurance',
        'reject_invalid_number',
        'reject_expired',
        'reject_name_mismatch',
        'reject_insufficient_cover',
        'reject_cannot_verify',
    ]
    readonly_fields = (
        'id', 'tradie_profile', 'insurance_type',
        'insurer_name', 'holder_name',
        'issued_at', 'expires_at',
        'verified_at', 'created_at', 'updated_at',
        'coverage_display_panel', 'document_preview_panel',
        'reminder_30d_sent_at', 'reminder_14d_sent_at',
        'reminder_7d_sent_at', 'reminder_1d_sent_at',
    )
    fields = (
        'tradie_profile', 'insurance_type',
        'insurer_name', 'policy_number', 'holder_name',
        'coverage_display_panel',
        'document_preview_panel',
        'issued_at', 'expires_at',
        'status', 'rejection_reason', 'rejection_note',
        'verified_at', 'created_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            status__in=['pending', 'in_review']
        ).select_related('tradie_profile')

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    # ── List columns ─────────────────────────────────────────────

    def policy_number_col(self, obj):
        return mark_safe(
            f'<code style="font-size:12px;font-weight:700;background:#F4EEDD;'
            f'padding:3px 8px;border-radius:6px">{obj.policy_number}</code>'
        )
    policy_number_col.short_description = 'Policy #'

    def insurance_type_col(self, obj):
        labels = {
            'public_liability':       ('PL', '#C5563A', '#F5EDE9'),
            'workers_compensation':   ('WC', '#0077AA', '#E0F4FF'),
            'professional_indemnity': ('PI', '#5B3FA6', '#EEE8FF'),
        }
        label, color, bg = labels.get(obj.insurance_type, (obj.insurance_type, '#7A6558', '#F0EDE8'))
        return mark_safe(
            f'<span style="padding:2px 8px;border-radius:8px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">{label}</span>'
        )
    insurance_type_col.short_description = 'Type'

    def coverage_col(self, obj):
        amt = obj.coverage_amount_cents / 100
        color = "#2E7D5A" if amt >= 20_000_000 else "#B85C00"
        return mark_safe(
            f'<span style="color:{color};font-weight:700">${amt:,.0f}</span>'
        )
    coverage_col.short_description = 'Coverage'

    def business_name_col(self, obj):
        try:
            return obj.tradie_profile.business_name
        except Exception:
            return "—"
    business_name_col.short_description = 'Business'

    def status_col(self, obj):
        return status_badge(obj.status)
    status_col.short_description = 'Status'

    def document_col(self, obj):
        if obj.document_url:
            return mark_safe('<span style="color:#2E7D5A;font-weight:700">📄 Yes</span>')
        return mark_safe('<span style="color:#A89080;font-size:11px">None</span>')
    document_col.short_description = 'Cert of Currency'

    def days_waiting(self, obj):
        if not obj.created_at:
            return "—"
        delta = (timezone.now() - obj.created_at).days
        color = "#A33030" if delta > 3 else "#B85C00" if delta > 1 else "#2E7D5A"
        return mark_safe(f'<span style="color:{color};font-weight:700">{delta}d</span>')
    days_waiting.short_description = 'Waiting'

    # ── Detail view rendered panels ───────────────────────────────

    def coverage_display_panel(self, obj):
        amt   = obj.coverage_amount_cents / 100
        color = "#2E7D5A" if amt >= 20_000_000 else "#B85C00"
        note  = (
            "✓ Meets the $20M minimum for licensed trades."
            if amt >= 20_000_000
            else "⚠️ Below the $20M minimum — verify with admin manager before approving."
        )
        return mark_safe(
            f'<div style="margin:4px 0">'
            f'  <span style="font-size:22px;font-weight:700;color:{color}">'
            f'    ${amt:,.0f}'
            f'  </span>'
            f'  <br>'
            f'  <span style="font-size:12px;color:#7A6558">{note}</span>'
            f'</div>'
        )
    coverage_display_panel.short_description = '💰 Coverage Amount'

    def document_preview_panel(self, obj):
        return photo_preview_html(obj.document_url, "View Certificate of Currency")
    document_preview_panel.short_description = '📄 Certificate of Currency'

    # ── Bulk actions ──────────────────────────────────────────────

    @admin.action(description="✅ Approve selected insurance policies")
    def approve_insurance(self, request, queryset):
        now       = timezone.now()
        count     = 0
        activated = []
        for policy in queryset.select_related('tradie_profile'):
            policy.status      = 'verified'
            policy.verified_at = now
            policy.save(update_fields=['status', 'verified_at', 'updated_at'])
            count += 1
            note = _maybe_activate_business_from_insurance(policy)
            if note:
                activated.append(note)
        msg = f"{count} insurance policy/policies approved."
        if activated:
            msg += " " + " | ".join(activated)
        self.message_user(request, msg)

    @admin.action(description="❌ Reject — Invalid policy number")
    def reject_invalid_number(self, request, queryset):
        self._bulk_reject(request, queryset, 'invalid_number')

    @admin.action(description="❌ Reject — Policy expired")
    def reject_expired(self, request, queryset):
        self._bulk_reject(request, queryset, 'expired')

    @admin.action(description="❌ Reject — Name mismatch (holder ≠ business)")
    def reject_name_mismatch(self, request, queryset):
        self._bulk_reject(request, queryset, 'name_mismatch')

    @admin.action(description="❌ Reject — Insufficient coverage (below $20M)")
    def reject_insufficient_cover(self, request, queryset):
        self._bulk_reject(request, queryset, 'insufficient_cover')

    @admin.action(description="❌ Reject — Cannot verify (insurer unreachable / document unclear)")
    def reject_cannot_verify(self, request, queryset):
        self._bulk_reject(request, queryset, 'cannot_verify')

    def _bulk_reject(self, request, queryset, reason: str):
        now     = timezone.now()
        updated = queryset.update(
            status='rejected',
            rejection_reason=reason,
            verified_at=now,
        )
        self.message_user(
            request,
            f"{updated} insurance policy/policies rejected ({reason}). "
            f"Business owner will be notified by email within 2 minutes.",
        )


# ═══════════════════════════════════════════════════════════════════════════
# NEW: TEAM MEMBERS — READ-ONLY WORKER OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════

@admin.register(TeamMember)
class TeamMemberAdmin(ReadOnlyAdmin):
    """
    Read-only view of all workers across all businesses.
    Use this to:
      - See which workers are NOT yet can_accept_jobs (need certs verified)
      - Check no_show_count for repeat offenders
      - See selfie upload status (safety gate for account sharing)
      - Identify device_id anomalies (multiple devices = potential account sharing)
    """
    list_display    = ('full_name', 'email', 'role_col', 'business_name_col',
                       'can_accept_jobs', 'is_active',
                       'selfie_col', 'jobs_completed', 'no_show_col',
                       'rating_col', 'created_at')
    list_filter     = ('role', 'is_active', 'can_accept_jobs')
    search_fields   = ('full_name', 'email', 'business__business_name')
    readonly_fields = ('id', 'business', 'user_id', 'full_name', 'email',
                       'phone_real', 'role', 'is_active', 'can_accept_jobs',
                       'avatar_url', 'selfie_url', 'device_id',
                       'jobs_completed', 'rating_avg',
                       'no_show_count', 'response_time_avg_min',
                       'last_login_at', 'location_updated_at',
                       'created_at', 'updated_at')
    list_select_related = ('business',)
    ordering        = ('-created_at',)

    def role_col(self, obj):
        color = "#C5563A" if obj.role == 'owner' else "#5B3FA6"
        bg    = "#F5EDE9" if obj.role == 'owner' else "#EEE8FF"
        return mark_safe(
            f'<span style="padding:2px 8px;border-radius:8px;background:{bg};'
            f'color:{color};font-size:11px;font-weight:700">{obj.role}</span>'
        )
    role_col.short_description = 'Role'

    def business_name_col(self, obj):
        try:
            return obj.business.business_name
        except Exception:
            return "—"
    business_name_col.short_description = 'Business'

    def selfie_col(self, obj):
        if obj.selfie_url:
            return mark_safe(
                f'<a href="{obj.selfie_url}" target="_blank" '
                f'   style="color:#2E7D5A;font-size:11px;font-weight:700">📷 View</a>'
            )
        return mark_safe(
            '<span style="color:#A33030;font-size:11px;font-weight:700">⚠️ Missing</span>'
        )
    selfie_col.short_description = 'Selfie'

    def no_show_col(self, obj):
        if obj.no_show_count == 0:
            return mark_safe('<span style="color:#2E7D5A">0</span>')
        color = "#A33030" if obj.no_show_count >= 3 else "#B85C00"
        return mark_safe(
            f'<span style="color:{color};font-weight:700">{obj.no_show_count}</span>'
        )
    no_show_col.short_description = 'No-shows'

    def rating_col(self, obj):
        if not obj.rating_avg:
            return mark_safe('<span style="color:#A89080;font-size:11px">—</span>')
        avg = float(obj.rating_avg)
        color = "#2E7D5A" if avg >= 4 else "#B85C00" if avg >= 3 else "#A33030"
        return mark_safe(f'<span style="color:{color};font-weight:700">{avg:.1f} ★</span>')
    rating_col.short_description = 'Rating'