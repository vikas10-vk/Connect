import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const FASTAPI_BASE =
    process.env.INTERNAL_API_URL ||
    (process.env.NODE_ENV === "development" ? "http://fastapi:8000" : process.env.NEXT_PUBLIC_API_URL) ||
    "http://localhost:8000";

const IS_PROD = process.env.NODE_ENV === "production";

// All three cookies share the refresh-token lifetime. The access-token JWT
// still enforces its own short expiry via the `exp` claim; the cookie only
// needs to outlive it so the proxy can present it and trigger a refresh.
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

const ACCESS_COOKIE = "access_token";
const REFRESH_COOKIE = "refresh_token";
const CSRF_COOKIE = "csrf_token";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
    return proxyRequest(request, (await ctx.params).path, "GET");
}
export async function POST(request: NextRequest, ctx: Ctx) {
    return proxyRequest(request, (await ctx.params).path, "POST");
}
export async function PUT(request: NextRequest, ctx: Ctx) {
    return proxyRequest(request, (await ctx.params).path, "PUT");
}
export async function PATCH(request: NextRequest, ctx: Ctx) {
    return proxyRequest(request, (await ctx.params).path, "PATCH");
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
    return proxyRequest(request, (await ctx.params).path, "DELETE");
}

function randomToken(): string {
    return crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");
}

async function proxyRequest(request: NextRequest, pathSegments: string[], method: Method) {
    const path = (pathSegments || []).join("/");
    const search = request.nextUrl.search || "";
    const targetUrl = `${FASTAPI_BASE}/api/v1/${path}${search}`;

    const cookieStore = await cookies();
    const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
    const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
    const csrfCookie = cookieStore.get(CSRF_COOKIE)?.value;

    const isLogin = path === "auth/login";
    const isRegister = path === "auth/register";
    const isRefresh = path === "auth/refresh";
    const isLogout = path === "auth/logout" || path === "auth/logout-all";
    const capturesTokens = isLogin || isRefresh;

    const isUnsafe =
        method === "POST" || method === "PUT" || method === "PATCH" || method === "DELETE";

    // -- CSRF double-submit check -----------------------------------------------
    // Enforced for unsafe methods only when a session cookie is present (an
    // unauthenticated request cannot abuse the victim's session). Login and
    // register have no session yet and are exempt.
    if (isUnsafe && accessToken && !isLogin && !isRegister) {
        const headerToken = request.headers.get("x-csrf-token");
        if (!csrfCookie || !headerToken || headerToken !== csrfCookie) {
            return NextResponse.json({ detail: "CSRF validation failed" }, { status: 403 });
        }
    }

    // -- Headers ---------------------------------------------------------------
    const headers: Record<string, string> = {};
    const incomingContentType = request.headers.get("content-type");
    if (incomingContentType) {
        headers["Content-Type"] = incomingContentType;
    } else if (method === "POST" || method === "PUT" || method === "PATCH") {
        headers["Content-Type"] = "application/json";
    }
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    } else {
        const incomingAuth = request.headers.get("authorization");
        if (incomingAuth) headers["Authorization"] = incomingAuth;
    }

    // -- Body ------------------------------------------------------------------
    let body: BodyInit | undefined;
    if (method === "POST" || method === "PUT" || method === "PATCH") {
        if (incomingContentType?.includes("multipart/form-data")) {
            try {
                body = await request.arrayBuffer();
            } catch {
                /* no body */
            }
        } else {
            let text = "";
            try {
                text = await request.text();
            } catch {
                /* no body */
            }
            // The refresh token lives only in an HttpOnly cookie - inject it
            // into the JSON body for the endpoints that need it.
            if (isRefresh || isLogout) {
                let parsed: Record<string, unknown> = {};
                if (text) {
                    try {
                        parsed = JSON.parse(text);
                    } catch {
                        parsed = {};
                    }
                }
                if (refreshToken) parsed.refresh_token = refreshToken;
                text = JSON.stringify(parsed);
                headers["Content-Type"] = "application/json";
            }
            if (text) body = text;
        }
    }

    // -- Proxy to FastAPI ------------------------------------------------------
    let upstream: Response;
    try {
        upstream = await fetch(targetUrl, { method, headers, body, redirect: "follow" });
    } catch (error) {
        console.error(`[PROXY] ${method} ${targetUrl} failed:`, error);
        return NextResponse.json({ detail: "Upstream service unavailable" }, { status: 503 });
    }

    const status = upstream.status;
    const contentType = upstream.headers.get("Content-Type") || "application/json";
    let responseBody = status === 204 ? "" : await upstream.text();
    const ok = status >= 200 && status < 300;

    // -- Cookie handling -------------------------------------------------------
    let tokensToSet: { access: string; refresh: string; csrf: string } | null = null;
    let clearCookies = false;

    if (isLogout) {
        clearCookies = true;
    } else if (capturesTokens && ok) {
        try {
            const data = JSON.parse(responseBody);
            if (data && data.access_token && data.refresh_token) {
                // Preserve the CSRF token across refreshes; mint a new one on login.
                const csrfValue = !isLogin && csrfCookie ? csrfCookie : randomToken();
                tokensToSet = {
                    access: data.access_token,
                    refresh: data.refresh_token,
                    csrf: csrfValue,
                };
                // Never hand the raw tokens back to browser JavaScript.
                delete data.access_token;
                delete data.refresh_token;
                responseBody = JSON.stringify(data);
            }
        } catch {
            /* non-JSON success body - nothing to capture */
        }
    }

    const res = new NextResponse(status === 204 ? null : responseBody, {
        status,
        headers: { "Content-Type": contentType },
    });

    if (clearCookies) {
        for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE]) {
            res.cookies.set(name, "", { path: "/", maxAge: 0 });
        }
    } else if (tokensToSet) {
        res.cookies.set(ACCESS_COOKIE, tokensToSet.access, {
            httpOnly: true,
            secure: IS_PROD,
            sameSite: "lax",
            path: "/",
            maxAge: COOKIE_MAX_AGE,
        });
        res.cookies.set(REFRESH_COOKIE, tokensToSet.refresh, {
            httpOnly: true,
            secure: IS_PROD,
            sameSite: "lax",
            path: "/",
            maxAge: COOKIE_MAX_AGE,
        });
        res.cookies.set(CSRF_COOKIE, tokensToSet.csrf, {
            httpOnly: false,
            secure: IS_PROD,
            sameSite: "lax",
            path: "/",
            maxAge: COOKIE_MAX_AGE,
        });
    }

    return res;
}
