# API Architecture — Verified Findings & Applied Fixes

**Project:** Hipages Marketplace (Next.js frontend + FastAPI backend)
**Review Date:** 2026-05-13
**Status:** All immediate fixes applied ✅ | Remaining items: production roadmap

---

## What Was Verified Against Real Code

Before any fix was written, the following files were read and confirmed against the stated issues:

| File | Confirmed Issue |
|---|---|
| `frontend/app/api/upload-photo/route.ts` | Used `NEXT_PUBLIC_API_URL` only — breaks in Docker ✅ |
| `frontend/app/api/proxy/[...path]/route.ts` | Correctly uses `INTERNAL_API_URL` — good ✅ |
| `frontend/src/lib/auth-context.tsx` | Older duplicate missing `expected_role`, `email_verified`, `verification_status`, `fetchUser` ✅ |
| `frontend/src/contexts/AuthContext.tsx` | Canonical, correct version — all pages already import from here ✅ |
| `frontend/src/lib/api.ts` | 401 interceptor logs out immediately, no refresh attempt ✅ |
| `backend/main.py` | `suburbs_router` mounted without `/api/v1` prefix ✅ |
| `frontend/app/api/suburbs/route.ts` | Called `/suburbs/search` matching the wrong mount path ✅ |
| `frontend/app/tradie/preferences/page.tsx` | `Promise.all` — one failure hides which category failed ✅ |

**Import audit result:** All 22 production files import from `src/contexts/AuthContext` (the canonical version). Zero files import from `src/lib/auth-context`. The duplicate was orphaned but still a risk for future developers.

---

## Fixes Applied (Code Changes)

### Fix 1 — Upload Route: Missing `INTERNAL_API_URL`

**File:** `frontend/app/api/upload-photo/route.ts`

**Root cause:** The presign call inside the upload handler used `NEXT_PUBLIC_API_URL || localhost:8000`. Inside a Docker container, `localhost:8000` refers to the Next.js container itself, not FastAPI. This causes presign to fail silently in production.

**Before:**
```ts
const FASTAPI_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
```

**After:**
```ts
const FASTAPI_BASE =
  process.env.INTERNAL_API_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://fastapi:8000' : process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8000';
```

**Why this order matters:**
- `INTERNAL_API_URL` is the Docker service name (e.g. `http://fastapi:8000`) — always set this in production
- `NEXT_PUBLIC_API_URL` is the browser-facing URL — only safe as server-side fallback for bare local dev
- `localhost:8000` is the last resort for developers who aren't running Docker at all

**Required env config:**
```env
# docker-compose.yml or production secrets
INTERNAL_API_URL=http://fastapi:8000
NEXT_PUBLIC_API_URL=https://yourdomain.com
```

---

### Fix 2 — Duplicate Auth Context Eliminated

**File:** `frontend/src/lib/auth-context.tsx`

**Root cause:** Two independent `AuthContext` implementations existed. The older one at `src/lib/auth-context.tsx` was missing:
- `expected_role` parameter in `login()` — needed for role-separated login pages
- `fetchUser` on the context object — needed for OTP / email-verify flows
- `email_verified`, `is_verified`, `verification_status` on the `User` type
- Pydantic v2 error array extraction (only extracted `detail` string, not `detail[].msg`)

**Verification:** All 22 production files already import from the correct `src/contexts/AuthContext`. The old file was a latent risk for future developers.

**Fix:** Replaced the old file entirely with a documented re-export barrel:
```ts
// src/lib/auth-context.tsx — now just re-exports the canonical version
export {
  AuthProvider,
  useAuth,
  type UserRole,
  type User,
  type TradieProfile,
} from '../contexts/AuthContext'
```

Any new file that accidentally imports from the old path will now get the correct, current implementation automatically.

---

### Fix 3 — Silent Token Refresh on 401

**File:** `frontend/src/lib/api.ts`

**Root cause:** The Axios response interceptor on 401 immediately cleared the token and redirected to login. If the user's access token simply expired mid-session (which happens after every token lifetime boundary), they were kicked out even though a silent refresh would have recovered the session.

**Before:** Any 401 → clear cookie → redirect to login.

**After (implemented):**

```
401 received on protected route
    ↓
Is another refresh in flight? → yes → queue this request, wait for token
    ↓ no
Call /api/proxy/auth/refresh with current refresh_token cookie
    ↓ success
Store new access_token (and refresh_token if rotated)
Replay all queued requests with new token
    ↓ refresh 401/error
Clear both tokens → redirect to login with session=expired
```

Key implementation details:
- **Queue pattern** prevents N simultaneous 401s from firing N refresh calls. The first one refreshes; the rest wait and replay with the new token.
- **Auth endpoints are excluded** (`/auth/login`, `/auth/refresh`, `/auth/register`) — these never trigger a recursive refresh loop.
- **`/auth/me` 401** is treated as a clean logout (no token at all), not a refresh trigger.
- Refresh token rotation is supported: if the backend returns a new `refresh_token`, it is stored.

**Backend requirement:** The `/auth/refresh` endpoint should accept either:
- A `refresh_token` field in the JSON body, OR
- An `HttpOnly` cookie (if you move to HTTP-only cookies later — see roadmap below)

---

### Fix 4 — Suburbs Router Moved to `/api/v1`

**Files:**
- `backend/main.py`
- `frontend/app/api/suburbs/route.ts`

**Root cause:** The suburbs router was mounted at root (`app.include_router(suburbs_router)`) while its own prefix is `/suburbs`, giving paths like `/suburbs/search`. Every other API router is under `/api/v1/...`. This inconsistency makes the API harder to secure, document, and version.

**Backend fix:**
```python
# main.py
app.include_router(suburbs_router, prefix="/api/v1")
# Result: /api/v1/suburbs/search, /api/v1/suburbs/postcode/{code}, etc.
```

**Frontend fix:**
```ts
// app/api/suburbs/route.ts
const res = await fetch(`${BACKEND_URL}/api/v1/suburbs/search?${params.toString()}`, { ... });
```

**No other frontend changes needed:** All suburb autocomplete calls go through the Next.js proxy at `/api/suburbs`, which is the only file that directly calls the FastAPI suburbs endpoint. That proxy was updated.

---

### Fix 5 — Silent Save Failures in Tradie Preferences

**File:** `frontend/app/tradie/preferences/page.tsx`

**Root cause:** The `saveChanges` function used `Promise.all` for category add/remove calls. `Promise.all` fails fast — if the first category add succeeds and the second fails, the first save is applied to the database but the UI either shows a generic error OR (depending on timing) shows success. In either case, the user cannot tell which service was or wasn't saved. For a job-matching platform, this means a tradie may appear matched for services they didn't successfully register, or miss matches for services they believe they have.

**Before:**
```ts
await Promise.all([
  ...toAdd.map(id => api.post(`/categories/my-categories/${id}`)),
  ...toRemove.map(id => api.delete(`/categories/my-categories/${id}`)),
  api.patch('/tradies/preferences/me', { ...settings, service_suburbs: serviceAreas }),
]);
toast.success('Preferences saved.');   // shown even if some calls failed
```

**After:** Uses `Promise.allSettled` and reports three distinct outcomes:

| Scenario | User sees |
|---|---|
| All operations succeeded | `"Preferences saved."` ✅ |
| Everything failed | `"Could not save preferences. Please check your connection and try again."` ❌ |
| Partial failure | `"Partially saved — 2 services could not be added; notification settings could not be saved. Please retry."` ⚠️ |

Local state baseline is updated only for the operations that actually succeeded, so retrying the save will only reattempt what genuinely failed.

---

## Remaining Production Roadmap

These are architectural improvements that go beyond single-file fixes. They are listed in recommended implementation order.

### 1. HTTP-Only Cookies for Auth Tokens (Security)

**Current risk:** `access_token` is stored in a JavaScript-readable cookie via `js-cookie`. Any XSS vulnerability (in a third-party library, a user-generated content render, or a CDN script) can exfiltrate this token.

**Target flow:**
1. Backend sets `access_token` and `refresh_token` as `HttpOnly; Secure; SameSite=Lax` cookies on the `/auth/login` response.
2. Frontend JavaScript never reads the token — it just calls the API.
3. The Next.js proxy forwards cookies automatically (`withCredentials: true` is already set).
4. Backend validates the cookie on every request.
5. Logout calls `POST /auth/logout` which clears the cookies server-side.

**FastAPI change needed:**
```python
response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    secure=True,        # HTTPS only
    samesite="lax",
    max_age=86400,      # 1 day
    path="/",
)
```

**Frontend change:** Remove all `Cookies.set/get/remove("access_token")` calls from `auth.ts` and `api.ts`. The cookie is managed entirely by the browser and backend.

---

### 2. Idempotency Keys for Critical POST Actions

Without idempotency keys, a double-click, a network retry, or a browser back/forward can create:
- Duplicate job postings
- Duplicate quotes
- Duplicate payment checkouts
- Duplicate lead distributions

**Implementation pattern:**

Frontend — generate and attach a key per user action:
```ts
// Generate once per user-initiated action, not per API call
const idempotencyKey = crypto.randomUUID();

api.post('/jobs', jobData, {
  headers: { 'Idempotency-Key': idempotencyKey }
});
```

Backend — store the key in Redis with a TTL, return the cached response on replay:
```python
@router.post("/jobs")
async def create_job(
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
    ...
):
    if idempotency_key:
        cached = await redis.get(f"idem:{idempotency_key}")
        if cached:
            return JSONResponse(json.loads(cached))   # replay stored response
    
    # ... create job
    result = {...}
    
    if idempotency_key:
        await redis.setex(f"idem:{idempotency_key}", 86400, json.dumps(result))
    
    return result
```

**Endpoints that must have this:** `POST /jobs`, `POST /quotes`, `POST /payments/checkout`, `POST /leads/accept`, `POST /auth/register`.

---

### 3. Outbox Pattern for Lead Distribution

**Current risk:** Job posting commits to the database, then triggers Celery lead distribution as a best-effort call. If Celery is down, overloaded, or the task is dropped, the job exists in the database but tradies never receive it. The homeowner sees success but nothing happens.

**Production-safe flow (transactional outbox):**

```
POST /jobs
  ↓
BEGIN transaction
  Insert job row
  Insert outbox_event row { type: "lead_distribution_requested", job_id: X, status: "pending" }
COMMIT
  ↓
Worker polls outbox_events WHERE status = 'pending'
  ↓
Worker processes event → creates leads → marks outbox_event status = 'done'
  ↓
If worker fails → event stays 'pending' → retried on next poll
```

**Benefit:** If Celery crashes between job creation and lead distribution, the outbox row survives. When Celery restarts, it picks up all pending events. No silent failures, no lost jobs.

**DB schema addition:**
```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, done, failed
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,
    error TEXT
);
```

---

### 4. Match Audit Trail

Every job match decision should be recorded so you can answer: "Why didn't Dave Plumbing get this job?"

**Schema:**
```sql
CREATE TABLE match_audit (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(id),
    detected_service VARCHAR(200),
    total_candidates INTEGER,
    matched INTEGER,
    excluded JSONB,   -- [{tradie_id, reason}]
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Excluded reasons to capture:** `service_mismatch`, `outside_radius`, `not_verified`, `suspended`, `no_credits`, `already_received_lead`.

**Value:** Support team can answer tradie complaints in seconds. Product team can measure match quality. Engineering can debug edge cases without guessing.

---

### 5. Request Tracing and Observability

Every request should carry an `X-Request-ID` from frontend through proxy to FastAPI. When a user reports a bug, you should be able to search Sentry or your log aggregator by that ID and see the full chain.

**Frontend (api.ts):**
```ts
api.interceptors.request.use((config) => {
    config.headers['X-Request-ID'] = crypto.randomUUID();
    // ... existing token attachment
    return config;
});
```

**Next.js proxy (route.ts):** Forward the header:
```ts
const requestId = request.headers.get('x-request-id') || crypto.randomUUID();
headers['X-Request-ID'] = requestId;
```

**FastAPI middleware:**
```python
@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

**Structured log on every request:** `{request_id, user_id, path, status, duration_ms, job_id (if present)}`.

---

### 6. Production Health Checks

Extend the existing `/health` endpoint:

```python
@app.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    checks = {}
    
    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
    
    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
    
    # Required env vars
    missing = [v for v in ["DATABASE_URL", "SECRET_KEY", "INTERNAL_API_URL"] if not os.getenv(v)]
    checks["env"] = "ok" if not missing else f"missing: {missing}"
    
    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if all_ok else "degraded", "checks": checks},
                        status_code=200 if all_ok else 503)
```

**Docker / Kubernetes:** Configure `readinessProbe` to call `/health/ready`. Only send traffic to instances that return 200.

---

### 7. Strict Production Environment Config

In production, missing required environment variables should crash startup loudly rather than falling back to dev defaults.

**FastAPI (config.py):**
```python
import os, sys

REQUIRED_PROD_VARS = ["DATABASE_URL", "SECRET_KEY", "REDIS_URL", "R2_BUCKET", "R2_ACCESS_KEY"]

if os.getenv("ENV") == "production":
    missing = [v for v in REQUIRED_PROD_VARS if not os.getenv(v)]
    if missing:
        print(f"FATAL: Missing required environment variables: {missing}", file=sys.stderr)
        sys.exit(1)
```

**Next.js:** Use `next.config.js` `env` validation or a startup check in `instrumentation.ts`.

This prevents the silent "works in dev, broken in prod" class of failures.

---

## Architecture Target State

```
Browser
  │
  ▼  Single Axios client (api.ts)
  │  — auth header, request ID, timeout, silent refresh
  │
  ▼  Next.js API Gateway (/api/proxy/*)
  │  — cookie forwarding, INTERNAL_API_URL, multipart passthrough
  │
  ▼  FastAPI
  │  — /api/v1/* (all routers, including suburbs)
  │  — idempotency keys on critical POSTs
  │  — request ID middleware
  │  — outbox events on job post
  │
  ├──▶ PostgreSQL (job, lead, outbox_event, match_audit rows)
  │
  ├──▶ Redis (idempotency cache, session, rate limiting)
  │
  ├──▶ Celery Workers
  │      — consume outbox_events
  │      — lead distribution with retry
  │      — email / SMS notifications
  │
  └──▶ R2 Storage (via presign, server-to-server only)

Observability layer (cross-cutting):
  — X-Request-ID on every request end-to-end
  — Structured logs (structlog / loguru)
  — Sentry for errors (frontend + backend)
  — Health check endpoints (/health/live, /health/ready)
  — Match audit table for debugging
```

---

## Priority Checklist

| # | Fix | Status |
|---|---|---|
| 1 | Upload route uses INTERNAL_API_URL | ✅ Applied |
| 2 | Duplicate auth context eliminated | ✅ Applied |
| 3 | Silent token refresh in Axios | ✅ Applied |
| 4 | Suburbs router under /api/v1 | ✅ Applied |
| 5 | Partial save failures surfaced in UI | ✅ Applied |
| 6 | HTTP-only cookies for auth | 📋 Roadmap |
| 7 | Idempotency keys on critical POSTs | 📋 Roadmap |
| 8 | Outbox pattern for lead distribution | 📋 Roadmap |
| 9 | Match audit trail | 📋 Roadmap |
| 10 | Request tracing / Sentry | 📋 Roadmap |
| 11 | Health check /ready endpoint | 📋 Roadmap |
| 12 | Strict prod env var validation | 📋 Roadmap |
