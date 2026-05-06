from django.db import models


# ── Users ─────────────────────────────────────────────────────────────────────

class User(models.Model):
    id          = models.CharField(max_length=36, primary_key=True)
    email       = models.EmailField(unique=True)
    full_name   = models.CharField(max_length=255)
    phone       = models.CharField(max_length=20, null=True, blank=True)
    role        = models.CharField(max_length=20)
    is_active   = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at  = models.DateTimeField()

    class Meta:
        managed  = False
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.role})"


# ── Tradie Profiles ───────────────────────────────────────────────────────────

class TradieProfile(models.Model):
    id                  = models.CharField(max_length=36, primary_key=True)
    user                = models.OneToOneField(User, on_delete=models.DO_NOTHING, db_column='user_id')
    business_name       = models.CharField(max_length=255)
    abn                 = models.CharField(max_length=20, null=True, blank=True)
    suburb              = models.CharField(max_length=100, null=True, blank=True)
    state               = models.CharField(max_length=50, null=True, blank=True)
    credits             = models.IntegerField(default=0)
    is_available        = models.BooleanField(default=True)
    avatar_url          = models.CharField(max_length=500, null=True, blank=True)
    logo_url            = models.CharField(max_length=500, null=True, blank=True)
    # Verification workflow fields (added by Alembic migration 004_verification)
    verification_status = models.CharField(max_length=30, default='pending_review')
    verification_notes  = models.TextField(null=True, blank=True)
    verified_at         = models.DateTimeField(null=True, blank=True)
    reviewed_at         = models.DateTimeField(null=True, blank=True)
    reviewed_by         = models.CharField(max_length=36, null=True, blank=True)
    # Team
    solo_or_team        = models.CharField(max_length=10, default='solo')
    team_size           = models.CharField(max_length=10, null=True, blank=True)
    # Ratings
    rating_avg          = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count        = models.IntegerField(default=0)
    created_at          = models.DateTimeField()

    class Meta:
        managed  = False
        db_table = 'tradie_profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.business_name} [{self.verification_status}]"


# ── Proxy: Verification Queue ─────────────────────────────────────────────────
# Shows in Django admin as a separate menu item — "⏳ Pending Verification"

class PendingVerification(TradieProfile):
    """Proxy model — same table, filtered to pending_review in admin."""
    class Meta:
        proxy        = True
        verbose_name = "⏳ Pending Verification"
        verbose_name_plural = "⏳ Pending Verification Queue"


# ── Categories ────────────────────────────────────────────────────────────────

class Category(models.Model):
    id   = models.CharField(max_length=36, primary_key=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True)
    level = models.IntegerField(default=1)
    parent_id = models.CharField(max_length=36, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed             = False
        db_table            = 'categories'
        verbose_name_plural = 'categories'
        ordering            = ['name']

    def __str__(self):
        return self.name


# ── Jobs ──────────────────────────────────────────────────────────────────────

class Job(models.Model):
    id          = models.CharField(max_length=36, primary_key=True)
    homeowner   = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='homeowner_id')
    category    = models.ForeignKey(Category, on_delete=models.DO_NOTHING, db_column='category_id')
    title       = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    suburb      = models.CharField(max_length=100, null=True, blank=True)
    state       = models.CharField(max_length=50, null=True, blank=True)
    status      = models.CharField(max_length=20)
    urgency     = models.CharField(max_length=50, null=True, blank=True)
    budget_min  = models.FloatField(null=True, blank=True)
    budget_max  = models.FloatField(null=True, blank=True)
    is_deleted  = models.BooleanField(default=False)
    lead_task_id = models.CharField(max_length=36, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField()
    updated_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.status}]"


# ── Leads ─────────────────────────────────────────────────────────────────────

class Lead(models.Model):
    id              = models.CharField(max_length=36, primary_key=True)
    job             = models.ForeignKey(Job, on_delete=models.DO_NOTHING, db_column='job_id')
    tradie          = models.ForeignKey(TradieProfile, on_delete=models.DO_NOTHING, db_column='tradie_id')
    credits_charged = models.IntegerField(default=1)
    status          = models.CharField(max_length=20)
    sent_at         = models.DateTimeField()

    class Meta:
        managed  = False
        db_table = 'leads'
        ordering = ['-sent_at']

    def __str__(self):
        return f"Lead → {self.job}"


# ── Reviews ───────────────────────────────────────────────────────────────────

class Review(models.Model):
    id          = models.CharField(max_length=36, primary_key=True)
    job         = models.ForeignKey(Job, on_delete=models.DO_NOTHING, db_column='job_id')
    homeowner   = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='homeowner_id', related_name='reviews_written')
    tradie      = models.ForeignKey(TradieProfile, on_delete=models.DO_NOTHING, db_column='tradie_id')
    rating      = models.IntegerField()
    comment     = models.TextField(null=True, blank=True)
    # Moderation fields (added by Alembic migration review_moderation)
    status      = models.CharField(max_length=20, default='pending')  # pending | approved | rejected
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=36, null=True, blank=True)
    created_at  = models.DateTimeField()

    class Meta:
        managed  = False
        db_table = 'reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}★ [{self.status}] — {self.job}"


# ── Proxy: Review Moderation Queue ───────────────────────────────────────────

class PendingReview(Review):
    """Proxy model — same table, filtered to status='pending' in admin."""
    class Meta:
        proxy        = True
        verbose_name = "⭐ Pending Review"
        verbose_name_plural = "⭐ Review Moderation Queue"


# ── Audit Events ──────────────────────────────────────────────────────────────

class AuditEvent(models.Model):
    id          = models.BigAutoField(primary_key=True)
    entity_type = models.CharField(max_length=50, null=True, blank=True)
    entity_id   = models.CharField(max_length=100, null=True, blank=True)
    actor_id    = models.CharField(max_length=36, null=True, blank=True)
    actor_role  = models.CharField(max_length=30, null=True, blank=True)
    action      = models.CharField(max_length=20)        # HTTP method
    path        = models.CharField(max_length=500)
    status_code = models.IntegerField(null=True, blank=True)
    ip_address  = models.CharField(max_length=45, null=True, blank=True)
    user_agent  = models.CharField(max_length=500, null=True, blank=True)
    created_at  = models.DateTimeField()

    class Meta:
        managed             = False
        db_table            = 'audit_events'
        ordering            = ['-created_at']
        verbose_name        = 'Audit Event'
        verbose_name_plural = '🔍 Audit Log'

    def __str__(self):
        return f"{self.action} {self.path} ({self.actor_role})"


# ── Job Events ────────────────────────────────────────────────────────────────

class JobEvent(models.Model):
    id         = models.BigAutoField(primary_key=True)
    job        = models.ForeignKey(Job, on_delete=models.DO_NOTHING, db_column='job_id', related_name='events')
    actor_id   = models.CharField(max_length=36)
    actor_role = models.CharField(max_length=30)
    action     = models.CharField(max_length=50)
    old_value  = models.JSONField(null=True, blank=True)
    new_value  = models.JSONField(null=True, blank=True)
    note       = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed             = False
        db_table            = 'job_events'
        ordering            = ['-created_at']
        verbose_name        = 'Job Event'
        verbose_name_plural = '📋 Job Events'

    def __str__(self):
        return f"{self.action} — job {self.job_id}"

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

