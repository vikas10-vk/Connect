"""
admin/core/models_additions.py

INSTRUCTION: Merge these model classes into your existing admin/core/models.py.
Add them after your existing model definitions. Then add the new models to the
imports in admin/core/admin.py (see updated admin.py).

All models are managed=False — Django reads them, Alembic/FastAPI writes them.
Django will never try to CREATE or ALTER these tables.

IMPORTANT — verified_by:
  The tradie_certifications.verified_by column is a FK to users.id (FastAPI UUIDs).
  Django admin users are in a different table and have no FastAPI UUID.
  We do NOT write to verified_by from Django admin — it stays NULL for
  admin-approved items. verified_at IS written (timezone.now()).
  The Django admin LogEntry table records which admin user performed each action.
  This is your full audit trail for admin approvals.
"""

from django.db import models


# ── TradieCertification ───────────────────────────────────────────────────────

class TradieCertification(models.Model):
    """Mirrors the tradie_certifications PostgreSQL table."""

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('in_review', 'In Review'),
        ('verified',  'Verified'),
        ('rejected',  'Rejected'),
        ('expired',   'Expired'),
    ]

    REJECTION_REASON_CHOICES = [
        ('invalid_number', 'Invalid number — not found in registry'),
        ('expired',        'Expired — licence has lapsed'),
        ('name_mismatch',  'Name mismatch — holder name does not match registry'),
        ('wrong_category', 'Wrong category — licence is for a different trade'),
        ('cannot_verify',  'Cannot verify — registry unavailable or photo unclear'),
        ('other',          'Other — see rejection note'),
    ]

    id                   = models.CharField(max_length=36, primary_key=True)

    # XOR FK — one of these is set, the other is NULL
    tradie_profile       = models.ForeignKey(
        'TradieProfile',
        on_delete=models.CASCADE,
        null=True, blank=True,
        db_column='tradie_profile_id',
        related_name='certifications',
    )
    team_member_id       = models.CharField(max_length=36, null=True, blank=True)
    # team_member_id is a plain CharField (not ForeignKey) to avoid circular
    # dependency. Use TeamMember.objects.get(id=cert.team_member_id) when needed.

    category             = models.ForeignKey(
        'Category',
        on_delete=models.PROTECT,
        db_column='category_id',
        related_name='certifications',
    )

    licence_number       = models.CharField(max_length=100)
    issuing_state        = models.CharField(max_length=20)
    issuing_body         = models.CharField(max_length=100, null=True, blank=True)
    holder_name          = models.CharField(max_length=255)
    issued_at            = models.DateField(null=True, blank=True)
    expires_at           = models.DateField(null=True, blank=True)
    photo_url            = models.CharField(max_length=500, null=True, blank=True)

    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason     = models.CharField(max_length=50, choices=REJECTION_REASON_CHOICES, null=True, blank=True)
    rejection_note       = models.TextField(null=True, blank=True)

    # verified_by is a FK to users.id in FastAPI — left NULL for admin approvals.
    # Django admin LogEntry captures the approving admin's identity.
    verified_by          = models.CharField(max_length=36, null=True, blank=True)
    verified_at          = models.DateTimeField(null=True, blank=True)

    # Reminder ledger — managed by Celery beat, read-only in admin
    reminder_30d_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_14d_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_7d_sent_at  = models.DateTimeField(null=True, blank=True)
    reminder_1d_sent_at  = models.DateTimeField(null=True, blank=True)

    created_at           = models.DateTimeField()
    updated_at           = models.DateTimeField()

    class Meta:
        managed      = False
        db_table     = 'tradie_certifications'
        verbose_name = 'Trade Certification'
        verbose_name_plural = 'Trade Certifications'
        ordering     = ['created_at']

    def __str__(self):
        return f"{self.licence_number} [{self.issuing_state}] — {self.status}"


class PendingCertification(TradieCertification):
    """
    Proxy model for the Django admin certification verification queue.
    Filtered to pending + in_review only in the admin get_queryset().
    """
    class Meta:
        proxy        = True
        verbose_name = 'Pending Certification'
        verbose_name_plural = '⏳ Certification Verification Queue'


# ── InsurancePolicy ───────────────────────────────────────────────────────────

class InsurancePolicy(models.Model):
    """Mirrors the insurance_policies PostgreSQL table."""

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('in_review', 'In Review'),
        ('verified',  'Verified'),
        ('rejected',  'Rejected'),
        ('expired',   'Expired'),
    ]

    INSURANCE_TYPE_CHOICES = [
        ('public_liability',       'Public Liability'),
        ('workers_compensation',   "Workers' Compensation"),
        ('professional_indemnity', 'Professional Indemnity'),
    ]

    REJECTION_REASON_CHOICES = [
        ('invalid_number',     'Invalid number — policy not found with this insurer'),
        ('expired',            'Expired — policy has lapsed'),
        ('name_mismatch',      'Name mismatch — policy holder does not match business'),
        ('insufficient_cover', 'Insufficient cover — below minimum required amount'),
        ('cannot_verify',      'Cannot verify — insurer unreachable or document unclear'),
        ('other',              'Other — see rejection note'),
    ]

    id                    = models.CharField(max_length=36, primary_key=True)
    tradie_profile        = models.ForeignKey(
        'TradieProfile',
        on_delete=models.CASCADE,
        db_column='tradie_profile_id',
        related_name='insurance_policies',
    )

    insurance_type        = models.CharField(max_length=30, choices=INSURANCE_TYPE_CHOICES, default='public_liability')
    insurer_name          = models.CharField(max_length=255)
    policy_number         = models.CharField(max_length=100)
    coverage_amount_cents = models.BigIntegerField()
    holder_name           = models.CharField(max_length=255)
    issued_at             = models.DateField(null=True, blank=True)
    expires_at            = models.DateField()
    document_url          = models.CharField(max_length=500, null=True, blank=True)

    status                = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason      = models.CharField(max_length=50, choices=REJECTION_REASON_CHOICES, null=True, blank=True)
    rejection_note        = models.TextField(null=True, blank=True)

    # verified_by is a FK to users.id — left NULL for admin approvals (same reason as certs)
    verified_by           = models.CharField(max_length=36, null=True, blank=True)
    verified_at           = models.DateTimeField(null=True, blank=True)

    reminder_30d_sent_at  = models.DateTimeField(null=True, blank=True)
    reminder_14d_sent_at  = models.DateTimeField(null=True, blank=True)
    reminder_7d_sent_at   = models.DateTimeField(null=True, blank=True)
    reminder_1d_sent_at   = models.DateTimeField(null=True, blank=True)

    created_at            = models.DateTimeField()
    updated_at            = models.DateTimeField()

    class Meta:
        managed      = False
        db_table     = 'insurance_policies'
        verbose_name = 'Insurance Policy'
        verbose_name_plural = 'Insurance Policies'
        ordering     = ['created_at']

    def __str__(self):
        return f"{self.policy_number} [{self.insurance_type}] — {self.status}"

    @property
    def coverage_amount_display(self):
        """Returns coverage as formatted AUD string."""
        return f"${self.coverage_amount_cents / 100:,.2f}"


class PendingInsurance(InsurancePolicy):
    """
    Proxy model for the Django admin insurance verification queue.
    Filtered to pending + in_review only in the admin get_queryset().
    """
    class Meta:
        proxy        = True
        verbose_name = 'Pending Insurance Policy'
        verbose_name_plural = '🛡️  Insurance Verification Queue'


# ── TeamMember ────────────────────────────────────────────────────────────────

class TeamMember(models.Model):
    """Mirrors the team_members PostgreSQL table."""

    ROLE_CHOICES = [
        ('owner',  'Owner'),
        ('worker', 'Worker'),
    ]

    id               = models.CharField(max_length=36, primary_key=True)
    business         = models.ForeignKey(
        'TradieProfile',
        on_delete=models.CASCADE,
        db_column='business_id',
        related_name='team_members',
    )
    user_id          = models.CharField(max_length=36, null=True, blank=True)

    full_name        = models.CharField(max_length=255)
    email            = models.CharField(max_length=255, unique=True)
    phone_real       = models.CharField(max_length=20)
    phone_masked     = models.CharField(max_length=20, null=True, blank=True)
    avatar_url       = models.CharField(max_length=500, null=True, blank=True)
    selfie_url       = models.CharField(max_length=500, null=True, blank=True)
    role             = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')

    # Auth — hashed_password intentionally excluded from all admin views
    last_login_at    = models.DateTimeField(null=True, blank=True)
    device_id        = models.CharField(max_length=255, null=True, blank=True)

    # Live location — read-only in admin
    current_lat      = models.FloatField(null=True, blank=True)
    current_lng      = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    # Status gates
    is_active        = models.BooleanField(default=True)
    can_accept_jobs  = models.BooleanField(default=False)

    # Internal performance (never shown to users)
    jobs_completed        = models.IntegerField(default=0)
    rating_avg            = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    no_show_count         = models.IntegerField(default=0)
    response_time_avg_min = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    created_at       = models.DateTimeField()
    updated_at       = models.DateTimeField()

    class Meta:
        managed      = False
        db_table     = 'team_members'
        verbose_name = 'Team Member'
        verbose_name_plural = '👥 Team Members'
        ordering     = ['business_id', 'role', 'full_name']

    def __str__(self):
        return f"{self.full_name} [{self.role}]"