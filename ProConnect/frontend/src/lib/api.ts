import axios from "axios";

/**
 * Axios instance for all browser -> backend calls.
 *
 * Auth model (BFF / HttpOnly cookies):
 *  - The browser never holds tokens in JavaScript. Tokens live in HttpOnly
 *    cookies set by the Next.js proxy (app/api/proxy/[...path]/route.ts).
 *  - Requests to /api/proxy/* carry those cookies automatically (same origin
 *    + withCredentials). The proxy reads the access-token cookie and adds the
 *    Authorization header server-side.
 *  - CSRF: the proxy also sets a readable `csrf_token` cookie. For unsafe
 *    methods we echo it back in the X-CSRF-Token header (double-submit).
 */
const api = axios.create({
    baseURL: "/api/proxy",
    headers: { "Content-Type": "application/json" },
    withCredentials: true,
});

function readCookie(name: string): string | undefined {
    if (typeof document === "undefined") return undefined;
    const match = document.cookie
        .split("; ")
        .find((c) => c.startsWith(`${name}=`));
    return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : undefined;
}

// -- Request interceptor: echo the CSRF token on unsafe methods --------------
api.interceptors.request.use((config) => {
    const method = (config.method || "get").toLowerCase();
    if (["post", "put", "patch", "delete"].includes(method)) {
        const csrf = readCookie("csrf_token");
        if (csrf) (config.headers as any)["X-CSRF-Token"] = csrf;
    }
    return config;
});

// -- Silent refresh state ----------------------------------------------------
let isRefreshing = false;
let refreshQueue: Array<() => void> = [];

function flushRefreshQueue() {
    refreshQueue.forEach((resolve) => resolve());
    refreshQueue = [];
}

function redirectToLogin() {
    if (typeof window === "undefined") return;
    const isTradie = window.location.pathname.startsWith("/tradie");
    window.location.href = isTradie ? "/tradie/login" : "/login";
}

// -- Response interceptor: silent refresh on 401 -----------------------------
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const status = error?.response?.status;
        const originalRequest: any = error?.config;
        const url: string = originalRequest?.url ?? "";

        const isAuthEndpoint =
            url.includes("/auth/login") ||
            url.includes("/auth/refresh") ||
            url.includes("/auth/register");

        // Non-401, or a 401 from the auth endpoints themselves - pass through.
        if (status !== 401 || isAuthEndpoint) {
            return Promise.reject(error);
        }

        // Guard against infinite retry loops.
        if (!originalRequest || originalRequest._retried) {
            return Promise.reject(error);
        }

        // The session probe (/auth/me) must never hard-redirect: a logged-out
        // visitor on a public page would otherwise be bounced to /login.
        const isSessionProbe = url.includes("/auth/me");

        if (isRefreshing) {
            return new Promise<void>((resolve) => refreshQueue.push(resolve)).then(() => {
                originalRequest._retried = true;
                return api(originalRequest);
            });
        }

        isRefreshing = true;
        try {
            // The proxy injects the HttpOnly refresh-token cookie into the body
            // and sets fresh cookies from the response - no token handling here.
            const csrf = readCookie("csrf_token");
            await axios.post(
                "/api/proxy/auth/refresh",
                {},
                {
                    withCredentials: true,
                    headers: csrf ? { "X-CSRF-Token": csrf } : {},
                }
            );
            flushRefreshQueue();
            originalRequest._retried = true;
            return api(originalRequest);
        } catch (refreshError) {
            refreshQueue = [];
            if (!isSessionProbe) redirectToLogin();
            return Promise.reject(refreshError);
        } finally {
            isRefreshing = false;
        }
    }
);

export default api;
