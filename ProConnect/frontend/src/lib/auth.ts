import api from "./api";

/**
 * Auth tokens are stored in HttpOnly cookies set by the Next.js proxy
 * (app/api/proxy) and are deliberately NOT readable from JavaScript.
 *
 * The proxy also sets a readable `csrf_token` cookie while a session is
 * active. Its presence is used purely as a cheap "there may be a session"
 * hint so we can skip the /auth/me probe for clearly-logged-out visitors.
 * It is NOT a security check - the server is always authoritative.
 */
export const hasSession = (): boolean => {
    if (typeof document === "undefined") return false;
    return document.cookie
        .split("; ")
        .some((c) => c.startsWith("csrf_token="));
};

export const fetchCurrentUser = async () => {
    const response = await api.get("/auth/me");
    return response.data;
};
