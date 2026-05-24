# CLAUDE.md — ProConnect (hipages) Project Reference

> **Purpose:** This file is the canonical reference for Claude (AI assistant) working on this codebase.
> Read this FIRST at the start of every session before making any changes. Update it after every significant fix.

---

## 1. What This App Is

**ProConnect** is an Australian tradie/homeowner marketplace (ProConnect-style).

**Full end-to-end flow (as of latest build):**
1. Homeowner posts a job (category + description + budget + contact details)
2. Backend distributes leads to matched, verified tradies (Celery task or in-process fallback)
3. Tradie receives the lead, views it, and submits a quote (price + message)
4. Homeowner views all quotes and accepts one → job moves to `hired`
5. Tradie clicks "Start job" (uploads before-photo) → job moves to `in_progress`
6. Tradie marks the job complete (uploads after-photo + optional note) → job moves to `completed`
7. Homeowner sees "Awaiting Confirmation" banner, clicks "Confirm complete" → job moves to `confirmed`
8. System auto-closes after payment window OR admin closes → job moves to `closed`

**Mid-job extras (also built):**
- Tradie can request a **scope change** (price/work increase) → homeowner approves/rejects → job returns to `in_progress`
- Tradie can **partial-stop** (stop mid-job) → admin reviews and decides partial charge
- Homeowner can **raise a dispute** on `completed` or `partial_stop` jobs (within 48 hours)
- Homeowner can **leave a review** after `completed`, `confirmed`, or `closed`

**Stack:**
- **Frontend:** Next.js 14 App Router — TypeScript, inline styles (no Tailwind), Axios (`src/lib/api.ts`), `js-cookie`, `sonner` toasts
- **Backend:** FastAPI + SQLAlchemy (async/asyncpg) + PostgreSQL — Python 3.11
- **Admin:** FastAPI admin router at `/api/v1/admin/*` — NO Django service (was removed as duplicate)
- **Tasks:** Celery + Redis (lead distribution, notifications) — in-process background task fallback when Celery is down
- **Email:** Resend (`services/resend_service.py`) — `_send_raw_email`, `_base_html`, `_btn`, `_first`, `APP_NAME`

---

## 2. Directory Map

```
ProConnect/
├── frontend/
│   ├── app/
│   │   ├── book/page.tsx                  # Homeowner job posting wizard (5-step + inline OTP for new users)
│   │   ├── login/page.tsx                 # Homeowner + admin login (role-aware redirect, no session-expiry banner)
│   │   ├── dashboard/
│   │   │   ├── page.tsx                   # Homeowner dashboard shell — redirects admin→/admin, tradie→/tradie/dashboard
│   │   │   └── HomeownerDashboardView.tsx # Main dashboard: jobs list + detail panel
│   │   ├── admin/page.tsx                 # Admin panel (single-page, tab-based, FastAPI-backed)
│   │   ├── verify-email/page.tsx          # OTP email verification page
│   │   └── tradie/
│   │       ├── login/page.tsx             # Tradie-specific login (no session-expiry banner)
│   │       ├── dashboard/page.tsx         # Tradie main hub — tabs: Overview/Leads/Active/Licences
│   │       ├── jobs/page.tsx              # Tradie jobs page (Active / Completed tabs) — has MarkCompleteModal
│   │       ├── preferences/page.tsx       # Service areas + categories + notifications
│   │       ├── profile/page.tsx           # Profile editor (no availability toggle — removed)
│   │       ├── licences/page.tsx          # Licence & doc uploads
│   │       └── onboarding/page.tsx        # First-time setup wizard
│   └── src/
│       ├── constants/
│       │   ├── categories.ts              # TRADIE_CATEGORIES (24 items), getCategorySlug(), CATEGORY_SLUG_MAP
│       │   └── problems.ts               # PROBLEM_SUGGESTIONS, detectCategory()
│       ├── contexts/AuthContext.tsx       # user, tradieProfile, UserRole ('homeowner'|'tradie'|'admin')
│       │                                  # logout() always routes to '/' for all roles
│       ├── lib/
│       │   ├── api.ts                    # Axios → /api/proxy/[...path] → FastAPI :8000
│       │   │                             # 401 interceptor: silent redirect (no ?session=expired banner)
│       │   └── tradie-verification.ts    # getServiceRule(), getRequiredDocuments(), getLevelLabel()
│       └── components/tradie/
│           ├── TradieStudioLayout.tsx    # Shared sidebar shell for all tradie pages
│           ├── MarkCompleteModal.tsx     # Shared modal: after-photo upload + complete job
│           ├── ai/AIChatInterface.tsx    # AI chat component
│           ├── Sidebar.tsx
│           └── Navbar.tsx
│
├── backend/
│   ├── main.py                           # FastAPI app, middleware stack, router registration
│   ├── routers/
│   │   ├── jobs.py                       # /jobs/* — full lifecycle
│   │   ├── quotes.py                     # /quotes/* — submit, view, accept/reject
│   │   ├── tradies.py                    # /tradies/* — profile, preferences, dashboard, certs
│   │   ├── categories.py                 # /categories/* — list, my-categories CRUD
│   │   ├── leads.py                      # /leads/*
│   │   ├── auth.py                       # /auth/login, /auth/me, /auth/register, /auth/refresh
│   │   │                                 # /auth/send-email-otp, /auth/verify-email-otp, /auth/resend-email-otp
│   │   └── admin.py                      # /admin/* — admin panel API (replaces Django)
│   ├── tasks/
│   │   └── lead_tasks.py                 # _distribute_leads(), _notify_tradies_new_lead()
│   ├── services/
│   │   ├── resend_service.py             # Email helpers (single send_tradie_suspended_email — duplicate removed)
│   │   └── job_state_machine.py          # JobStateMachine — ALL status changes go through here
│   ├── models/                           # SQLAlchemy ORM models
│   │   ├── job.py                        # Job model + JobStatus enum (includes CONFIRMED)
│   │   ├── job_photo.py                  # JobPhoto model — job_photos table (job_id, url, file_key)
│   │   ├── job_event.py                  # Audit trail — every status change logged
│   │   └── ...
│   ├── schemas/
│   │   └── quote_schema.py              # QuoteCreate, QuoteResponse (tradie_name, phone, etc.)
│   ├── scripts/                          # One-time DB fix scripts (run inside Docker)
│   │   ├── apply_db_fixes.py            # Creates job_events table + moves open→quoted jobs
│   │   ├── fix_accepted_to_in_progress.py
│   │   └── check_quotes_state.py
│   ├── create_admin.py                   # ← CLI tool to create/promote/demote admin users
│   ├── middleware/
│   │   ├── rate_limit.py                 # Redis sliding-window rate limiter (100 req/min default)
│   │   ├── audit_middleware.py           # Auto-logs all mutating requests to audit_events table
│   │   ├── request_id.py                 # Attaches X-Request-ID to every request
│   │   └── security_headers.py          # Security headers middleware
│   └── seeds/
│       └── seed_categories.py           # Source of truth for category slugs
│
└── CLAUDE.md                            # ← YOU ARE HERE
```

---

## 3. Job State Machine

**Single rule: ALL job status changes go through `JobStateMachine` in `services/job_state_machine.py`.**
Never set `job.status = ...` directly outside of that file.

### Full state flow:

```
open → quoted → hired → in_progress → completed → confirmed → closed
                  ↓           ↓              ↓
              cancelled   partial_stop    disputed
                              ↓              ↓
                         completed ←────── closed (admin)
                         disputed
                              ↓
                            closed (admin)

in_progress → awaiting_scope_approval → in_progress (homeowner approves/rejects)
                                      ↓
                                  partial_stop (system timeout + tradie chose to stop)
```

### Who can trigger which transition:

| Transition | Actor | How |
|---|---|---|
| `open → quoted` | system | Lead distribution task |
| `open → cancelled` | homeowner, system | Cancel before quotes |
| `quoted → hired` | homeowner | Accepts a quote |
| `quoted → cancelled` | homeowner, system | Cancel during quoting |
| `hired → in_progress` | tradie, system | `POST /jobs/{id}/start` (with before-photo) |
| `hired → cancelled` | homeowner, tradie, system | Cancel after hire |
| `in_progress → awaiting_scope_approval` | tradie | `POST /jobs/{id}/scope-change` |
| `in_progress → partial_stop` | tradie | `POST /jobs/{id}/partial-stop` |
| `in_progress → completed` | tradie | `POST /jobs/{id}/complete` (with after-photo) |
| `awaiting_scope_approval → in_progress` | homeowner, system | `POST /jobs/{id}/scope-change/respond` |
| `partial_stop → completed` | homeowner, admin | Admin resolves or homeowner accepts partial |
| `partial_stop → disputed` | homeowner | `POST /jobs/{id}/dispute` |
| `completed → confirmed` | homeowner | `POST /jobs/{id}/confirm-complete` |
| `completed → disputed` | homeowner | `POST /jobs/{id}/dispute` (within 48h) |
| `completed → closed` | system, admin | Auto-close after 48h no dispute |
| `confirmed → closed` | system, admin | Auto-close after payment release |
| `disputed → closed` | admin | Admin resolves dispute |

### Critical gotchas with the state machine:

1. **`job_events` table must exist** — if missing, every state machine transition silently rolls back. Run `apply_db_fixes.py` once after fresh deploy.
2. **The `confirm_complete` endpoint does NOT use the state machine** — it updates `job.status` directly via ORM. This is intentional (avoids JobEvent dependency for a simple homeowner confirmation).
3. **Partial write bug (historical)** — An earlier version of `confirm_complete` committed `confirmed_by_user_at` separately from `status`. The endpoint now self-heals: if `confirmed_by_user_at` is set but `status` is still `"completed"`, it repairs the status to `"confirmed"` on the next call.

---

## 4. Admin System

### How admin users work:
- There is **no separate admin login page** — admin users log in through the regular homeowner login page (`/login`)
- After login, if `user.role === 'admin'`, the frontend silently redirects to `/admin`
- If an admin somehow lands on `/dashboard`, it also redirects to `/admin`
- The admin portal is never exposed or mentioned in the homeowner UI (security by obscurity)

### Admin panel tabs (frontend/app/admin/page.tsx):

| Tab | Key | What it shows |
|---|---|---|
| Overview | `overview` | Stats cards (tradies, homeowners, jobs, disputes, verifications) |
| Tradies | `tradies` | Search/filter tradies, verify/suspend/email actions |
| Homeowners | `homeowners` | Search homeowners, view account details |
| Verification | `verification` | Pending certs, insurance docs, profile change requests |
| Jobs | `jobs` | All jobs with status filter, before/after photo thumbnails |
| **Completed** | `completed` | **Finished jobs (completed/confirmed/closed) — full detail panel** |
| Disputes | `disputes` | Open disputes, resolution actions |
| Reviews | `reviews` | All reviews with approve/hide/delete actions |

### Admin panel — Completed Jobs tab (NEW):
- **Endpoint:** `GET /admin/completed-jobs?page&limit&status&search`
- **Statuses shown:** `completed`, `confirmed`, `closed`
- **Each job card shows:** title, category, suburb, tradie business name, quote amount, status pill, star rating badge, photo count badge
- **Expandable detail panel** (click row to open):
  - Job details (title, description, category, location, urgency, ID)
  - Timeline (posted, completed, confirmed by homeowner, last updated)
  - Homeowner section (name, email, phone)
  - Tradie section (business name, full name, email, phone, accepted quote amount + message, verification status)
  - Work evidence (before photo + after photos with thumbnail previews, completion note)
  - Homeowner review (stars, comment, timestamp, status pill)
- **Status display:** `confirmed` and `closed` both display as **"Completed"** in status pills (they are further along the state machine than `completed`)

### StatusPill display mapping:

| Internal status | Displayed label | Color |
|---|---|---|
| `completed` | Completed | Green |
| `confirmed` | Completed | Green |
| `closed` | Completed | Green |
| `in_progress` | In Progress | Blue |
| `hired` | Hired | Blue |
| `open` | Open | Amber |
| `disputed` | Disputed | Red |
| `verified` | Verified | Green |
| `rejected` | Rejected | Red |
| `suspended` | Suspended | Red |
| `cancelled` | Cancelled | Grey |

### Creating admin users:
Admin users must be created/promoted via CLI — they **cannot** sign up through the normal UI (which only allows `homeowner` or `tradie` roles).

```bash
# Run inside the fastapi container
docker compose -f docker-compose.dev.yml exec fastapi python create_admin.py create \
  --email owner@yourdomain.com \
  --name "Owner Name"
# Bootstrap token and password are prompted interactively.

# Other commands:
python create_admin.py promote --email owner@yourdomain.com  # owner allowlist + token required
python create_admin.py demote  --email admin@example.com     # admin → homeowner
python create_admin.py list                                   # list all admin users
```

---

## 5. OTP Email Verification Flow

### When it's used:
- On first registration via the **Book a Job** wizard (Step 5) — new users register inline without leaving the page
- On the `/verify-email` standalone page

### OTP API endpoints (all require logged-in user):

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/send-email-otp` | Send 6-digit OTP to user's email |
| POST | `/auth/verify-email-otp` | Verify with `{ code: string }` body |
| POST | `/auth/resend-email-otp` | Resend OTP to same email |

### Book page inline OTP flow (book/page.tsx Step 5):
1. User fills in name, email, password → clicks "Create Account & Continue"
2. `handleRegisterAndSendOtp()`: creates account (auto-logs in) → calls `POST /auth/send-email-otp` → sets `otpSent = true`
3. OTP screen appears inline (no redirect) — user enters 6-digit code
4. `handleVerifyOtpAndPost()`: calls `POST /auth/verify-email-otp` → on success calls `postJob()` → redirects to `/dashboard`
5. Resend code button calls `POST /auth/resend-email-otp`

### Login flow (existing users at Step 5):
- No OTP needed for returning users — `handleFinalSubmit()` logs in and posts the job directly

---

## 6. Auth & Session Behaviour

### Token storage:
- JWT tokens stored in cookies: `access_token` and `refresh_token`
- `src/lib/auth.ts` handles `saveToken`, `removeToken`, `getToken`

### Session expiry (silent redirect — no banner):
- When a 401 is received by the Axios interceptor in `src/lib/api.ts`, `redirectToLogin()` is called
- It clears both cookies silently and redirects:
  - `/tradie/*` paths → `/tradie/login`
  - All others → `/login`
- **There is NO `?session=expired` query param** and **no session-expired banner** on login pages
- Login pages (`login/page.tsx`, `tradie/login/page.tsx`) do NOT read any session-expiry param

### Logout behaviour:
- `logout()` in `AuthContext.tsx` always routes to `'/'` (home page) for ALL roles (homeowner, tradie, admin)
- This is intentional — all roles share the same logout destination

### Role-based redirects after login:

| Role | Redirect destination |
|---|---|
| `homeowner` | `/dashboard` |
| `tradie` | `/tradie/dashboard` |
| `admin` | `/admin` |

Also enforced defensively in:
- `dashboard/page.tsx` — redirects admin/tradie away from homeowner dashboard
- `login/page.tsx` — role-check after successful login

---

## 7. Category System

### Canonical 24 categories (from `seed_categories.py`):

| Display Name | DB Slug |
|---|---|
| Plumbing | `plumbing` |
| Electrical | `electrical` |
| Carpentry & Joinery | `carpentry` |
| Painting & Decorating | `painting` |
| Tiling | `tiling` |
| Roofing | `roofing` |
| Air Conditioning & Heating | `hvac` |
| Landscaping & Gardening | `landscaping` |
| Concreting & Paving | `concreting` |
| Plastering | `plastering` |
| Flooring | `flooring` |
| Fencing & Gates | `fencing` |
| Glazing & Window Repairs | `glazing` |
| Pest Control | `pest-control` |
| Security Systems | `security` |
| Solar & Renewable Energy | `solar` |
| Gas Fitting | `gas-fitting` |
| Demolition | `demolition` |
| Waterproofing | `waterproofing` |
| Cleaning | `cleaning` |
| Handyman | `handyman` |
| Building & Construction | `building` |
| Bathroom Renovation | `bathroom-renovation` |
| Kitchen Renovation | `kitchen-renovation` |

**Always use `getCategorySlug()` from `src/constants/categories.ts` when posting jobs — never roll your own slug.**

---

## 8. Key API Endpoints

All frontend calls go through `/api/proxy/[...path]` → `http://fastapi:8000/api/v1/...`

### Auth endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Login — returns `access_token`. Accepts optional `expected_role` param |
| POST | `/auth/register` | Register new user |
| GET | `/auth/me` | Get current user (id, email, name, role) |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/send-email-otp` | Send OTP to logged-in user's email |
| POST | `/auth/verify-email-otp` | Verify OTP `{ code }` |
| POST | `/auth/resend-email-otp` | Resend OTP |

### Job lifecycle endpoints
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/jobs/` | Homeowner | Create job |
| GET | `/jobs/my-jobs` | Homeowner | List own jobs (with quotes, photos) |
| POST | `/jobs/{id}/start` | Tradie | Mark started — requires `photo_before_url`. `hired → in_progress` |
| POST | `/jobs/{id}/scope-change` | Tradie | Request scope change. `in_progress → awaiting_scope_approval` |
| POST | `/jobs/{id}/scope-change/respond` | Homeowner | Approve/reject scope change. `awaiting_scope_approval → in_progress` |
| POST | `/jobs/{id}/complete` | Tradie | Mark complete — requires `photo_after_urls` (1-3). `in_progress → completed` |
| POST | `/jobs/{id}/confirm-complete` | Homeowner | Confirm job done. `completed → confirmed` |
| POST | `/jobs/{id}/partial-stop` | Tradie | Stop mid-job. `in_progress → partial_stop` |
| POST | `/jobs/{id}/dispute` | Homeowner | Raise dispute (within 48h). `completed/partial_stop → disputed` |
| POST | `/jobs/{id}/review` | Homeowner | Leave review (allowed on `completed`, `confirmed`, `closed`) |

### Admin endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/overview` | Stats (totals, pending counts) |
| GET | `/admin/tradies` | List tradies with search/filter/pagination |
| GET | `/admin/homeowners` | List homeowners |
| GET | `/admin/jobs` | All jobs with status filter, returns `photo_before_url`, `after_photos[]`, `completion_note` |
| GET | `/admin/completed-jobs` | Finished jobs (completed/confirmed/closed) with full homeowner+tradie+photos+review detail |
| GET | `/admin/verification` | Pending certs, insurance docs, profile change requests |
| GET | `/admin/disputes` | Open disputes |
| GET | `/admin/reviews` | All reviews |
| PATCH | `/admin/tradies/{id}/verify` | Approve/reject/suspend tradie |
| DELETE | `/admin/reviews/{id}` | Delete review |

### `GET /admin/completed-jobs` response shape (per job):
```json
{
  "id": "uuid",
  "title": "Fix Leaking Kitchen Tap",
  "status": "confirmed",
  "category": "Plumbing",
  "suburb": "Sydney",
  "state": "NSW",
  "postcode": "2000",
  "urgency": "asap",
  "description": "...",
  "created_at": "2026-05-10T...",
  "completed_at": "2026-05-14T...",
  "confirmed_by_user_at": "2026-05-15T...",
  "updated_at": "...",
  "photo_before_url": "https://...",
  "completion_note": "All done.",
  "after_photos": [{ "url": "https://...", "file_key": "..." }],
  "homeowner": { "name": "...", "email": "...", "phone": "..." },
  "tradie": {
    "business_name": "...", "full_name": "...", "email": "...", "phone": "...",
    "verification_status": "verified",
    "quote_amount": 200.0, "quote_message": "..."
  },
  "review": {
    "rating": 5, "comment": "Great job!", "status": "published", "created_at": "..."
  }
}
```

### Tradie endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/tradies/onboarding/status` | Profile + certs + insurance + `gates.profile_approved` |
| GET | `/tradies/profile/me` | `verification_status`, `business_name`, etc. |
| PATCH | `/tradies/profile/me` | Update profile |
| GET | `/tradies/preferences/me` | `service_suburbs`, notification prefs |
| PATCH | `/tradies/preferences/me` | Save preferences |
| GET | `/tradies/dashboard/me` | Returns leads array with `status` and `job_status` fields |
| GET | `/tradies/stats/me` | `avg_rating`, `review_count`, `credits` |
| GET | `/categories/my-categories` | This tradie's selected categories |
| GET | `/categories` | Flat list of all 24 canonical categories (public, no auth needed) |

---

## 9. Tradie Verification Status Flow

```
pending_review → in_review → verified   (admin approves)
                           → rejected
                           → suspended
                           → needs_documents
```

- **`isApproved`** = `verification_status === 'verified'`
- When approved: Leads + Active Jobs nav items appear in tradie sidebar
- **Never use `"approved"` as a status string** — the DB value is always `"verified"`

---

## 10. Frontend — MarkCompleteModal (Shared Component)

**File:** `frontend/src/components/tradie/MarkCompleteModal.tsx`

Used in both `tradie/dashboard/page.tsx` (Active tab) and `tradie/jobs/page.tsx` (Active jobs tab).

**Flow inside modal:**
1. Upload 1–3 after-photos via `POST /api/v1/uploads/photo` (multipart) → gets back `{url}`
2. Optional completion note textarea
3. "Mark complete" button → `POST /jobs/{jobId}/complete` with `{ photo_after_urls: string[], completion_note: string | null }`
4. On success → calls `onSuccess()` (parent reloads data)

---

## 11. Frontend — Homeowner Confirm Complete Flow

**File:** `frontend/app/dashboard/HomeownerDashboardView.tsx`

**Banner conditions:**
- `selectedJob.status === 'completed'` → shows "Tradie says the job is done" banner with "Confirm complete" and "Something's wrong" buttons
- `selectedJob.status === 'confirmed'` → shows "Job confirmed — thank you!" banner
- `selectedJob.status === 'disputed'` → shows DisputeBanner

---

## 12. All Fixes Made (Full Log)

### Fixes 1–32 (previous sessions — see git history for details)
1. **`categories.ts`** — 24 typed categories, `getCategorySlug()`, `CATEGORY_SLUG_MAP`
2. **`problems.ts`** — `detectCategory()` returns canonical names
3. **`book/page.tsx`** — uses `getCategorySlug()`, fixed slugs
4. **`quote_schema.py`** + `quotes.py` — added tradie contact fields to `QuoteResponse`
5. **`lead_tasks.py`** — `_notify_tradies_new_lead()` email, `job.status = "quoted"` after lead creation
6. **Admin emails** — verification approve/reject wired to email notifications
7. **Admin cert/insurance emails** — wired to emails
8. **`preferences/page.tsx`** — fixed `isApproved`, missing-docs warning banner
9. **`profile/page.tsx`** — full redesign with services, areas, certs, insurance
10. **`job_events` table** — `apply_db_fixes.py` creates table + fixes stuck jobs
11. **Quote accept 500 fix** — ORM → explicit SQL for job status
12. **Job stuck at "quoted"** — state machine transaction now works with `job_events` table
13. **Accept flow** — quote accept goes `quoted → hired`
14. **Leads badge count** — only counts `status === 'sent'` (unquoted)
15. **`create_quote` state machine** — replaced invalid transition with direct assignment
16. **`create_admin.py`** — CLI tool for admin user management
17. **Django admin service removed** — FastAPI admin router is the only admin backend
18. **`login/page.tsx` — admin login fix** — removed hardcoded `expected_role: 'homeowner'`
19. **`AuthContext.tsx`** — added `'admin'` as a valid `UserRole`
20. **`job_state_machine.py`** — added `completed→confirmed` and `confirmed→closed` transitions
21. **`models/job.py`** — added `JobStatus.CONFIRMED`
22. **`POST /jobs/{id}/confirm-complete`** — new endpoint with self-healing partial write fix
23. **`jobs.py` review endpoint** — allows review on `confirmed` status
24. **`HomeownerDashboardView.tsx`** — confirm complete UI with inline error, stale-closure fix
25. **`tradie/dashboard/page.tsx`** — `confirmed` badge in lead rows
26. **`MarkCompleteModal.tsx`** — new shared component for marking jobs complete
27. **`tradie/dashboard/page.tsx`** — MarkCompleteModal wired in Active jobs tab
28. **`tradie/jobs/page.tsx`** — MarkCompleteModal wired in Active jobs tab
29. **`preferences/page.tsx`** — category fix (flat list, not broken tree endpoint)
30. **`profile/page.tsx`** — category name resolution fix
31. **`profile/page.tsx`** — removed availability toggle from UI
32. **Admin bootstrap locked down** — `admin_security.py`, `OWNER_ADMIN_EMAILS`, `ADMIN_BOOTSTRAP_TOKEN`

### Fixes 33–41 (current session)

33. **`admin/page.tsx` — Mail icon import fix** — `Mail` was missing from lucide-react imports, crashing the Reviews tab with a TS reference error. Added to import list.

34. **`resend_service.py` — duplicate function removed** — `send_tradie_suspended_email` was defined twice (second definition silently overwrote first). Removed the dead first definition. Also renamed `notes` → `reason` parameter to match its caller in `admin.py`.

35. **`admin/page.tsx` + `admin.py` — tradie after-work photos in Jobs tab** — Admin's Jobs tab now shows before/after thumbnails inline in expandable rows. Backend `list_jobs` updated to include `photo_before_url`, `after_photos[]`, `completion_note` via `selectinload(Job.photos)`.

36. **`book/page.tsx` — inline OTP for first-time registration** — New users registering at Step 5 of the job wizard no longer get redirected to a separate verify-email page. Flow: register (auto-login) → OTP sent inline → OTP verified inline → job posted → redirect to `/dashboard`. Existing login users skip OTP entirely. New states: `otpSent`, `otpCode`, `otpVerified`, `otpError`, `otpLoading`. New handlers: `handleRegisterAndSendOtp()`, `handleVerifyOtpAndPost()`.

37. **`src/lib/api.ts` — silent session expiry redirect** — Removed `?session=expired&returnTo=...` from the 401 redirect. Now silently clears cookies and redirects to `/login` (homeowners) or `/tradie/login` (tradies). No banner.

38. **`login/page.tsx` + `tradie/login/page.tsx` — session-expired banner removed** — Both login pages no longer read or display a session-expiry message. Clean login pages.

39. **`dashboard/page.tsx` — admin redirect fix** — The homeowner dashboard auth guard now explicitly redirects `admin` role users to `/admin` (previously they'd land on the homeowner dashboard UI).

40. **`AuthContext.tsx` — logout to home for all roles** — `logout()` now always pushes to `'/'` regardless of role. Previously it pushed to `/login` which left admin users on the wrong page.

41. **`admin/page.tsx` + `admin.py` — Completed Jobs tab** — New tab showing all jobs with status `completed`, `confirmed`, or `closed`. Each card is clickable to expand a full detail panel with: job info, timeline, homeowner contact, tradie contact + accepted quote, before/after photo evidence, completion note, and homeowner review. Backend: new `GET /admin/completed-jobs` endpoint using `selectinload` for photos/review/homeowner and a bulk JOIN for accepted quote + tradie data.

42. **`admin/page.tsx` — StatusPill confirmed/closed → "Completed"** — `confirmed` and `closed` job statuses now display as "Completed" (green pill) since they represent fully finished jobs. The internal state values are unchanged — only the display label is normalised for admin readability. The Jobs tab filter dropdown still lets admin filter by the exact internal state.

### File corruption repairs (this session)
The following files had null-byte corruption (from previous edit tool operations) which caused TypeScript "Invalid character" errors. All were repaired by stripping null bytes:
- `frontend/app/login/page.tsx`
- `frontend/app/tradie/login/page.tsx`
- `frontend/app/tradie/dashboard/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/book/page.tsx` (also had content truncation — restored)
- `frontend/app/admin/page.tsx` (also had content truncation — restored)
- `frontend/app/verify-email/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/components/tradie/ai/AIChatInterface.tsx`

---

## 13. What Is NOT Built Yet (Remaining Tasks)

### 🟡 MEDIUM PRIORITY

**Scope change UI (tradie side)**
- Backend: `POST /jobs/{id}/scope-change` exists and works
- Homeowner response: `POST /jobs/{id}/scope-change/respond` exists
- No frontend UI for tradie to trigger a scope change request
- No frontend UI for homeowner to see/respond to a pending scope change notification

**Payment/credits system**
- Backend: `backend/routers/payments.py` exists
- No frontend payment UI built

**Tradie no-show reporting**
- No watchdog/GPS check-in UI

### 🟢 LOWER PRIORITY

**Admin dispute resolution UI**
- `disputed → closed` transition requires admin action
- Admin panel Disputes tab exists but needs full resolution flow

**Homeowner scope change notification**
- When job is in `awaiting_scope_approval`, homeowner needs push/banner to respond
- Currently no real-time notification — homeowner would have to refresh

---

## 14. Email Pattern

```python
from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME

await _send_raw_email(
    recipient_email,
    subject,
    _base_html(html_body, accent_color),   # accent_color is a hex string
    plain_text_fallback,
)
# Accent colors: "#2E7D5A" (green/approved), "#A8423A" (red/rejected), "#9A6B1E" (amber/warning)
```

All email calls must be **best-effort (non-fatal)** — always wrap in `try/except` and never let email failure break the main flow.

---

## 15. Pattern: Async email from sync context

```python
import asyncio

def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except Exception:
        try:
            asyncio.run(coro)
        except Exception:
            pass
```

---

## 16. Known Gotchas & Rules

| Rule | Detail |
|---|---|
| Never use `"approved"` as a status | DB value is always `"verified"` |
| Never run multiple SQL in one asyncpg execute | Split into separate `await db.execute()` calls |
| `job_events` table must exist | Run `apply_db_fixes.py` after fresh deploy |
| Phone in quotes | Only visible in `QuoteResponse.tradie_phone` after quote `status == "accepted"` |
| Category slugs | Always use `getCategorySlug()` — never hand-roll slugs |
| `isApproved` frontend | `verification_status === 'verified'` (from `/tradies/profile/me` or `onboarding/status`) |
| Lead distribution | Celery task with in-process fallback via `BackgroundTasks` |
| Strict-verification services | Require verified licence cert + public liability insurance |
| Admin login | Goes through `/login` (homeowner page) — silently redirected to `/admin` by role check |
| Admin on homeowner dashboard | `dashboard/page.tsx` auth guard also redirects admin → `/admin` |
| Admin user creation | Must use `create_admin.py` CLI with `OWNER_ADMIN_EMAILS` + private `ADMIN_BOOTSTRAP_TOKEN` |
| No Django admin | Django service was removed. Admin backend is `routers/admin.py` in FastAPI |
| `/tradies/categories/tree` | Avoid — can error in async context. Use `/categories` flat list instead |
| `alert()` in frontend | Browsers can block it silently. Use inline state-driven error banners instead |
| `useCallback` stale closures | If a callback reads state without it being a dep, use `useRef` to track current value |
| `confirm_complete` partial write | Endpoint self-heals: if `confirmed_by_user_at` set but `status != "confirmed"`, repairs on next call |
| Session expiry | Silent redirect — NO `?session=expired` param, NO banner on login pages |
| Logout destination | Always `'/'` for all roles (homeowner, tradie, admin) |
| `confirmed` / `closed` display | StatusPill shows both as "Completed" (green) — internal state unchanged, display-only normalisation |
| `resend_service.py` | Single `send_tradie_suspended_email` definition — never add a second one |
| File edit tool truncation | The Edit tool can truncate large files. After large edits, verify file line count with bash. If truncated, use Python binary append to restore. |
| Null bytes in files | Previous edit operations left null bytes. Run `data.replace(b'\x00', b'')` to clean if TS reports "Invalid character" errors |

---

## 17. Docker Services

```yaml
fastapi:   port 8000   # Backend API (uvicorn --reload)
nextjs:    port 3000   # Next.js frontend (next dev)
postgres:  port 5432   # PostgreSQL (user: tradie, password: tradie_dev_password, db: tradie_dev)
redis:     port 6379   # Redis
celery:               # Worker for lead_tasks (no exposed port)
```

**Note:** Django admin service was removed. There is no `django_admin` container.

**Restart after code changes:**
```bash
docker compose -f docker-compose.dev.yml restart fastapi
docker compose -f docker-compose.dev.yml restart nextjs
```

**Hard refresh browser after restart:** `Ctrl+Shift+R`

**One-time DB fixes (run once after fresh deploy):**
```bash
docker compose -f docker-compose.dev.yml exec fastapi python scripts/apply_db_fixes.py
docker compose -f docker-compose.dev.yml exec fastapi python scripts/fix_accepted_to_in_progress.py
```

**Create admin user:**
```bash
docker compose -f docker-compose.dev.yml exec fastapi python create_admin.py create \
  --email owner@yourdomain.com --name "Owner Name"
# Bootstrap token and password are prompted interactively.
```

---

*Last updated: 2026-05-16 — Fixes 1–42 complete. Job full lifecycle built end-to-end. Admin system with Completed Jobs tab built. OTP inline registration, silent session expiry, all file corruption repaired.*
