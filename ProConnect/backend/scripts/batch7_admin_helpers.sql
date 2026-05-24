-- ════════════════════════════════════════════════════════════════════════
-- BATCH 7 — admin SQL helpers
-- Run these in psql (port 5433) or DBeaver
-- ════════════════════════════════════════════════════════════════════════


-- ─── 1. BACKFILL EXISTING TRADIES' PREFERENCES ────────────────────────────
-- Any tradie who has a profile but no preferences row gets one auto-created
-- with their home suburb seeded. Run once after deploying Batch 7.

INSERT INTO tradie_preferences (tradie_id, service_suburbs, notify_email, notify_sms)
SELECT 
    p.id,
    json_build_array(
        json_build_object(
            'suburb',     p.suburb,
            'state_code', p.state,
            'postcode',   p.postcode,
            'label',      p.suburb || ' (' || p.state || ' ' || p.postcode || ')'
        )
    )::text,
    true,
    false
FROM tradie_profiles p
WHERE p.suburb IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM tradie_preferences tp WHERE tp.tradie_id = p.id
  );


-- ─── 2. APPROVE A TRADIE (manual admin approval) ──────────────────────────
-- Until the admin UI is built, use this to approve a tradie so they receive leads.
-- Replace the email below with the tradie you want to approve.

UPDATE tradie_profiles
SET verification_status = 'approved',
    is_available        = true,
    reviewed_at         = NOW()
WHERE user_id = (
    SELECT id FROM users WHERE email = 'madness.hack1000@gmail.com'
);


-- ─── 3. CHECK A TRADIE'S FULL STATE ───────────────────────────────────────
-- Useful for debugging "why didn't this tradie get a lead"

SELECT
    u.email,
    u.is_verified                AS email_verified,
    u.is_active,
    p.business_name,
    p.verification_status,
    p.is_available,
    p.suburb,
    p.state,
    p.lat,
    p.lng,
    p.radius_km,
    pref.service_suburbs,
    (SELECT array_agg(c.name)
     FROM tradie_categories tc
     JOIN categories c ON c.id = tc.category_id
     WHERE tc.tradie_id = p.id)  AS services
FROM users u
JOIN tradie_profiles p   ON p.user_id  = u.id
LEFT JOIN tradie_preferences pref ON pref.tradie_id = p.id
WHERE u.email = 'madness.hack1000@gmail.com';


-- ─── 4. SEE LEAD DISTRIBUTION FOR A RECENT JOB ────────────────────────────
-- After posting a homeowner job, run this to see which tradies got the lead.

SELECT
    j.title,
    j.suburb         AS job_suburb,
    j.state          AS job_state,
    j.created_at,
    p.business_name  AS tradie,
    p.suburb         AS tradie_suburb,
    l.status         AS lead_status,
    l.sent_at        AS lead_sent
FROM jobs j
LEFT JOIN leads l ON l.job_id = j.id
LEFT JOIN tradie_profiles p ON p.id = l.tradie_id
ORDER BY j.created_at DESC, l.sent_at
LIMIT 20;


-- ─── 5. WIPE LEADS FOR A JOB (to retry distribution) ──────────────────────
-- If you want to re-run lead distribution for a job (e.g. after fixing
-- a tradie's data), wipe the existing leads first.
-- Replace JOB_ID with the actual ID.

-- DELETE FROM leads WHERE job_id = 'JOB_ID_HERE';
