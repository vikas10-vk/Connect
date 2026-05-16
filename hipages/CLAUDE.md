# CLAUDE.md — ProConnect (hipages) Project Reference

> **Purpose:** This file is the canonical reference for Claude (AI assistant) working on this codebase.
> Read this FIRST at the start of every session before making any changes. Update it after every significant fix.

---

## 1. What This App Is

**ProConnect** is an Australian tradie/homeowner marketplace (hipages-style).

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
hipages/
├── frontend/
│   ├── app/
│   │   ├── book/page.tsx                  # Homeowner job posting wizard
│   │   ├── login/page.tsx                 # Homeowner + admin login (role-aware redirect)
│   │   ├── dashboard/
│   │   │   ├── page.tsx                   # Homeowner dashboard shell (sidebar + nav)
│   │   │   └── HomeownerDashboardView.tsx # Main dashboard: jobs list + detail panel
│   │   ├── admin/                         # Admin panel (custom FastAPI-backed UI)
│   │   └── tradie/
│   │       ├── login/page.tsx             # Tradie-specific login
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
│       ├── lib/
│       │   ├── api.ts                    # Axios → /api/proxy/[...path] → FastAPI :8000
│       │   └── tradie-verification.ts    # getServiceRule(), getRequiredDocuments(), getLevelLabel()
│       └── components/tradie/
│           ├── TradieStudioLayout.tsx    # Shared sidebar shell for all tradie pages
│           ├── MarkCompleteModal.tsx     # Shared modal: after-photo upload + complete job
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
│   │   └── admin.py                      # /admin/* — admin panel API (replaces Django)
│   ├── tasks/
│   │   └── lead_tasks.py                 # _distribute_leads(), _notify_tradies_new_lead()
│   ├── services/
│   │   ├── resend_service.py             # Email helpers
│   │   └── job_state_machine.py          # JobStateMachine — ALL status changes go through here
│   ├── models/                           # SQLAlchemy ORM models
│   │   ├── job.py                        # Job model + JobStatus enum (includes CONFIRMED)
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
- The admin portal is never exposed or mentioned in the homeowner UI (security by obscurity)

### Creating admin users:
Admin users must be created/promoted via CLI — they **cannot** sign up through the normal UI (which only allows `homeowner` or `tradie` roles).

Admin bootstrap is owner-locked:
- `OWNER_ADMIN_EMAILS` must contain the target email.
- `ADMIN_BOOTSTRAP_TOKEN` must be configured privately outside git.
- The matching token must be supplied interactively or via `ADMIN_BOOTSTRAP_TOKEN_INPUT`.
- Do not pass real bootstrap tokens as command arguments in shared shells or logs.

```bash
# Run inside the fastapi container
docker compose -f docker-compose.dev.yml exec fastapi python create_admin.py create \
  --email owner@yourdomain.com \
  --name "Owner Name"
# Bootstrap token and password are prompted interactively.

# Other commands:
python create_admin.py promote --email owner@yourdomain.com  # owner allowlist + token required
python create_admin.py demote  --email admin@example.com      # admin → homeowner
python create_admin.py list                                # list all admin users
```

### `create_admin.py` location:
`backend/create_admin.py` — uses `psycopg2` (sync), NOT asyncpg. Reads `SYNC_DATABASE_URL` or strips `+asyncpg` from `DATABASE_URL`. Admin create/promote calls `services/admin_security.py` before touching the database.

### `UserRole` type (frontend):
```typescript
// frontend/src/contexts/AuthContext.tsx
export type UserRole = 'homeowner' | 'tradie' | 'admin'
```

---

## 5. Category System

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

### Category API endpoints:
- `GET /categories` → flat array of `{id, name, slug, parent_id}` — **use this for name resolution and pickers**
- `GET /tradies/categories/tree` → nested tree with subcategories and service_questions — **avoid in preferences/profile** (can error if service_questions table has issues)
- `GET /categories/my-categories` → `[{category_id, tradie_id}]` for the logged-in tradie

**Always use `getCategorySlug()` from `src/constants/categories.ts` when posting jobs — never roll your own slug.**

---

## 6. Key API Endpoints

All frontend calls go through `/api/proxy/[...path]` → `http://fastapi:8000/api/v1/...`

### Auth endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Login — returns `access_token`. Accepts optional `expected_role` param |
| POST | `/auth/register` | Register new user |
| GET | `/auth/me` | Get current user (id, email, name, role) |
| POST | `/auth/refresh` | Refresh access token |

### Job lifecycle endpoints
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/jobs/` | Homeowner | Create job |
| GET | `/jobs/my-jobs` | Homeowner | List own jobs (with quotes, photos) |
| POST | `/jobs/{id}/start` | Tradie | Mark started — requires `photo_before_url` (optional). `hired → in_progress` |
| POST | `/jobs/{id}/scope-change` | Tradie | Request scope change. `in_progress → awaiting_scope_approval` |
| POST | `/jobs/{id}/scope-change/respond` | Homeowner | Approve/reject scope change. `awaiting_scope_approval → in_progress` |
| POST | `/jobs/{id}/complete` | Tradie | Mark complete — requires `photo_after_urls` (1-3). `in_progress → completed` |
| POST | `/jobs/{id}/confirm-complete` | Homeowner | Confirm job done. `completed → confirmed` |
| POST | `/jobs/{id}/partial-stop` | Tradie | Stop mid-job with reason + photo. `in_progress → partial_stop` |
| POST | `/jobs/{id}/dispute` | Homeowner | Raise dispute (within 48h). `completed/partial_stop → disputed` |
| POST | `/jobs/{id}/review` | Homeowner | Leave review (allowed on `completed`, `confirmed`, `closed`) |

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
| POST | `/categories/my-categories/{id}` | Add category |
| DELETE | `/categories/my-categories/{id}` | Remove category |
| GET | `/categories` | Flat list of all 24 canonical categories (public, no auth needed) |

### Quote endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/quotes/` | Tradie submits quote (lead_id, amount, message) |
| GET | `/quotes/my-quote/{lead_id}` | Tradie fetches their own quote |
| GET | `/quotes/job/{job_id}` | Homeowner fetches all quotes for their job |
| PATCH | `/quotes/{quote_id}/status` | Homeowner accepts/rejects (`?new_status=accepted`) |

### `GET /tradies/dashboard/me` response shape:
```json
{
  "leads": [
    {
      "id": "...",
      "status": "sent|quoted|accepted",
      "job_status": "open|quoted|hired|in_progress|completed|confirmed|closed",
      "job_id": "...",
      "job_title": "...",
      "job_suburb": "...",
      "tradie_id": "...",
      "quote_amount": 350.00
    }
  ]
}
```

---

## 7. Tradie Verification Status Flow

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

## 8. Frontend — MarkCompleteModal (Shared Component)

**File:** `frontend/src/components/tradie/MarkCompleteModal.tsx`

Used in both `tradie/dashboard/page.tsx` (Active tab) and `tradie/jobs/page.tsx` (Active jobs tab).

**Props:**
```typescript
interface MarkCompleteModalProps {
  jobId: string;
  jobTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}
```

**Flow inside modal:**
1. Upload 1–3 after-photos via `POST /api/v1/uploads/photo` (multipart) → gets back `{url}`
2. Optional completion note textarea
3. "Mark complete" button → `POST /jobs/{jobId}/complete` with `{ photo_after_urls: string[], completion_note: string | null }`
4. On success → calls `onSuccess()` (parent reloads data)

---

## 9. Frontend — Homeowner Confirm Complete Flow

**File:** `frontend/app/dashboard/HomeownerDashboardView.tsx`

**State:**
- `confirmingCompleteJobId: string | null` — tracks which job is in-flight
- `confirmError: string | null` — inline error message (replaces `alert()` which can be browser-blocked)
- `selectedJobIdRef: useRef<string | null>` — fixes stale closure in `loadData`'s `useCallback`

**Banner conditions:**
- `selectedJob.status === 'completed'` → shows "Tradie says the job is done" banner with "Confirm complete" and "Something's wrong" buttons
- `selectedJob.status === 'confirmed'` → shows "Job confirmed — thank you!" banner
- `selectedJob.status === 'disputed'` → shows DisputeBanner

**`handleConfirmComplete` logic:**
```typescript
// 1. Sets loading state + clears error
// 2. Calls POST /jobs/{jobId}/confirm-complete
// 3. On success: optimistically updates job status to 'confirmed' in local state
// 4. Then calls loadData() to re-fetch from server
// 5. On error: sets confirmError (shown as inline red banner — never uses alert())
// 6. Console.log for debugging: '[confirm-complete] Sending POST for job: ...'
```

---

## 10. Tradie Dashboard — Job Status Badges

**File:** `frontend/app/tradie/dashboard/page.tsx`

In the lead list (LeadRow component):
```tsx
{lead.job_status === 'confirmed' ?  <span>Confirmed</span>
: lead.job_status === 'completed' ? <span>Awaiting confirmation</span>
: lead.job_status === 'in_progress' ? <span>In Progress</span>
: ...}
```

---

## 11. TradieStudioLayout — Sidebar Badge Logic

File: `frontend/src/components/tradie/TradieStudioLayout.tsx`

```typescript
// Leads badge = leads where tradie hasn't quoted yet
setNewLeadCount(leads.filter(l => l.status === 'sent').length);

// Active Jobs badge = jobs currently in progress
setActiveJobCount(leads.filter(l => l.job_status === 'in_progress').length);
```

Both counts come from `GET /tradies/dashboard/me`.

---

## 12. All Fixes Made (Full Log)

### Fixes 1–15 (previous sessions)
1. **`categories.ts`** — 24 typed categories, `getCategorySlug()`, `CATEGORY_SLUG_MAP`
2. **`problems.ts`** — `detectCategory()` returns canonical names
3. **`book/page.tsx`** — uses `getCategorySlug()`, fixed slugs
4. **`quote_schema.py`** + `quotes.py` — added tradie contact fields to `QuoteResponse`
5. **`lead_tasks.py`** — `_notify_tradies_new_lead()` email, `job.status = "quoted"` after lead creation
6. **Admin emails** — verification approve/reject wired to email notifications
7. **Admin cert/insurance emails** — cert and insurance admin views wired to emails
8. **`preferences/page.tsx`** — fixed `isApproved`, missing-docs warning banner
9. **`profile/page.tsx`** — full redesign with services, areas, certs, insurance
10. **`job_events` table** — `apply_db_fixes.py` creates table + fixes stuck jobs
11. **Quote accept 500 fix** — ORM → explicit SQL for job status
12. **Job stuck at "quoted"** — state machine transaction now works with `job_events` table
13. **Accept flow** — quote accept goes `quoted → hired` (then tradie starts → `in_progress`)
14. **Leads badge count** — only counts `status === 'sent'` (unquoted)
15. **`create_quote` state machine** — replaced invalid transition with direct assignment

### Fixes 16–32

16. **`create_admin.py`** (NEW FILE) — CLI tool to create/promote/demote admin users using psycopg2 sync. Run inside Docker container. Bypasses the normal signup flow entirely.

17. **Django admin service removed** — Removed `django_admin` service from `docker-compose.dev.yml`. Was a duplicate. FastAPI admin router at `/api/v1/admin/*` is the only admin backend now.

18. **`login/page.tsx` — admin login fix** — Removed hardcoded `expected_role: 'homeowner'` from login call. After login, role-based redirect: admin → `/admin`, tradie → `/tradie/dashboard`, homeowner → `/dashboard`. Admin portal never mentioned in homeowner UI.

19. **`AuthContext.tsx` — `UserRole` type** — Added `'admin'` as a valid role: `'homeowner' | 'tradie' | 'admin'`

20. **`job_state_machine.py` — confirmed status** — Added two new transitions:
    - `("completed", "confirmed"): ["homeowner"]`
    - `("confirmed", "closed"): ["system", "admin"]`
    Plus transition notes for both.

21. **`models/job.py` — `JobStatus.CONFIRMED`** — Added `CONFIRMED = "confirmed"` to the Python enum for code consistency.

22. **`jobs.py` — `POST /jobs/{id}/confirm-complete`** (NEW ENDPOINT) — Homeowner confirms job complete. Sets `confirmed_by_user_at` and `status = "confirmed"`. Includes self-healing logic: if `confirmed_by_user_at` is already set but `status` is still `"completed"` (partial write from earlier bug), repairs the status and returns correctly.

23. **`jobs.py` — review endpoint** — Updated `job.status not in ("completed", "closed")` check to also include `"confirmed"` so homeowners can review after confirming.

24. **`HomeownerDashboardView.tsx` — confirm complete UI** — Added:
    - `confirmError` state (inline error — replaces `alert()` which can be browser-blocked)
    - `selectedJobIdRef` ref + `useEffect` sync (fixes stale closure bug in `loadData`)
    - Fixed `loadData`'s `useCallback` to use `selectedJobIdRef.current` instead of captured-at-mount `selectedJobId`
    - "Tradie says the job is done" confirm banner for `completed` status
    - "Job confirmed — thank you!" banner for `confirmed` status
    - Inline red error banner under confirm button (never uses browser `alert()`)
    - Optimistic status update before `loadData()` re-fetch

25. **`tradie/dashboard/page.tsx` — confirmed badge** — Added `confirmed` status badge in lead rows ("Confirmed" in sage green). `completed` shows "Awaiting confirmation" badge.

26. **`MarkCompleteModal.tsx`** (NEW FILE) — Shared modal component for tradie marking a job complete. Handles photo upload (1–3 photos) and optional completion note. Calls `POST /jobs/{id}/complete`.

27. **`tradie/dashboard/page.tsx` — MarkCompleteModal wired** — Active jobs tab now has "Mark complete" button that opens the modal. After success reloads lead data.

28. **`tradie/jobs/page.tsx` — MarkCompleteModal wired** — Active jobs tab has same "Mark complete" button and modal flow.

29. **`preferences/page.tsx` — categories fix** — Changed from broken `/tradies/categories/tree` (service_questions async error) to `/categories` flat list. Fixed data extraction: `data || []` instead of `data?.categories || []`.

30. **`profile/page.tsx` — category name resolution fix** — Changed tree call to `api.get('/categories')`. Categories are now displayed by name (e.g. "Plumbing"), never by UUID. Orphan IDs that can't resolve show "Service" as placeholder.

31. **`profile/page.tsx` — removed availability toggle** — Removed "Availability" toggle button from the edit form (phone field now spans full width). Removed "Available for work / Not available" status dot from profile header. The `is_available` field remains in the save payload (defaults `true`) but is no longer user-editable in the UI.

32. **Admin bootstrap locked down** — Added `services/admin_security.py` and updated `create_admin.py` so admin creation/promotion requires both `OWNER_ADMIN_EMAILS` and a private `ADMIN_BOOTSTRAP_TOKEN`. Normal signup still rejects `admin`; CLI creation is now owner-only unless someone has production secrets/DB access.

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
- `PATCH /tradies/availability/toggle` endpoint exists but availability toggle removed from UI

**Tradie no-show reporting**
- No watchdog/GPS check-in UI

### 🟢 LOWER PRIORITY

**Admin dispute resolution UI**
- `disputed → closed` transition requires admin action
- Admin panel needs a dispute queue view

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
| Admin user creation | Must use `create_admin.py` CLI with `OWNER_ADMIN_EMAILS` + private `ADMIN_BOOTSTRAP_TOKEN` — cannot sign up via UI |
| No Django admin | Django service was removed. Admin backend is `routers/admin.py` in FastAPI |
| `/tradies/categories/tree` | Avoid using this — can error in async context. Use `/categories` instead |
| `alert()` in frontend | Browsers can block it silently. Use inline state-driven error banners instead |
| `useCallback` stale closures | If a callback reads state without it being a dep, use `useRef` to track current value |
| `confirm_complete` partial write | Endpoint self-heals: if `confirmed_by_user_at` set but `status != "confirmed"`, repairs on next call |

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

*Last updated: 2026-05-16 — Fixes 1–32 complete. Job full lifecycle built end-to-end. Admin system built. Admin bootstrap locked to owner allowlist + private token.*
