import axios from "axios";
import Cookies from "js-cookie";

const api = axios.create({
    baseURL: "/api/proxy",
    headers: { "Content-Type": "application/json" },
    withCredentials: true,
});

// ── Request interceptor — attach token to every request ───────────────────────
api.interceptors.request.use((config) => {
    const token = Cookies.get("access_token");
    if (token) {
        config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
});

// ── Silent token refresh state ────────────────────────────────────────────────
// Tracks an in-flight refresh so parallel 401s share one refresh call
// instead of firing multiple /auth/refresh requests simultaneously.
let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

function processRefreshQueue(newToken: string) {
    refreshQueue.forEach((resolve) => resolve(newToken));
    refreshQueue = [];
}

function redirectToLogin() {
    Cookies.remove("access_token", { path: "/" });
    const isTradie = window.location.pathname.startsWith("/tradie");
    const loginPath = isTradie ? "/tradie/login" : "/login";
    const returnTo = encodeURIComponent(window.location.pathname);
    window.location.href = `${loginPath}?session=expired&returnTo=${returnTo}`;
}

// ── Response interceptor — silent refresh on 401, logout on refresh failure ───
api.interceptors.response.use(
    // Success — pass through unchanged
    (response) => response,

    // Error — attempt silent refresh before giving up
    async (error) => {
        const status = error?.response?.status;
        const url: string = error?.config?.url ?? "";

        // Skip refresh logic for auth endpoints themselves
        const isAuthEndpoint =
            url.includes("/auth/login") ||
            url.includes("/auth/refresh") ||
            url.includes("/auth/register");

        // Non-401 or auth endpoint errors — pass through immediately
        if (status !== 401 || isAuthEndpoint) {
            // Still redirect on /auth/me 401 (background session check) — token is simply gone
            if (status === 401 && url.includes("/auth/me")) {
                Cookies.remove("access_token", { path: "/" });
            }
            return Promise.reject(error);
        }

        // ── 401 on a protected route: attempt silent refresh ──────────────────
        const originalRequest = error.config;

        if (isRefreshing) {
            // Another refresh is already in flight — queue this request
            return new Promise<string>((resolve) => {
                refreshQueue.push(resolve);
            }).then((newToken) => {
                originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
                return api(originalRequest);
            });
        }

        isRefreshing = true;

        try {
            const refreshToken = Cookies.get("refresh_token");
            const refreshRes = await axios.post(
                "/api/proxy/auth/refresh",
                refreshToken ? { refresh_token: refreshToken } : {},
                { withCredentials: true }
            );

            const newToken: string = refreshRes.data.access_token;
            Cookies.set("access_token", newToken, {
                expires: 1,
                sameSite: "lax",
                path: "/",
            });

            // Store new refresh token if backend rotates it
            if (refreshRes.data.refresh_token) {
                Cookies.set("refresh_token", refreshRes.data.refresh_token, {
                    expires: 7,
                    sameSite: "lax",
                    path: "/",
                });
            }

            processRefreshQueue(newToken);

            // Retry the original failed request with the new token
            originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
            return api(originalRequest);

        } catch {
            // Refresh failed — session is truly expired, redirect to login
            refreshQueue = [];
            redirectToLogin();
            return Promise.reject(error);
        } finally {
            isRefreshing = false;
        }
    }
);

export default api;
