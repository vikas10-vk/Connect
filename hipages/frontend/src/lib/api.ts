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

// ── Response interceptor — handle expired / invalid token ─────────────────────
api.interceptors.response.use(
    // Success — pass through unchanged
    (response) => response,

    // Error — check if it's a 401
    (error) => {
        const status = error?.response?.status;
        const url = error?.config?.url ?? "";

        // Only auto-logout on 401, and never redirect on the login call itself
        // Also don't redirect on /auth/me (the background session check) to avoid kicking users off public pages
        if (status === 401 && !url.includes("/auth/login") && !url.includes("/auth/me")) {
            // Clear the expired token
            Cookies.remove("access_token", { path: "/" });

            // Redirect to the correct login page based on current route
            const isTradie = window.location.pathname.startsWith("/tradie");
            const loginPath = isTradie ? "/tradie/login" : "/login";
            const returnTo = encodeURIComponent(window.location.pathname);
            window.location.href = `${loginPath}?session=expired&returnTo=${returnTo}`;
        }

        return Promise.reject(error);
    }
);

export default api;