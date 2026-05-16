import Cookies from "js-cookie";
import api from "./api";

export const saveToken = (token: string) => {
    Cookies.set("access_token", token, {
        expires: 1,      // 1 day
        sameSite: "lax",
        path: "/",
    });
};

export const getToken = (): string | undefined => {
    return Cookies.get("access_token");
};

export const removeToken = () => {
    Cookies.remove("access_token", { path: "/" });
};

export const fetchCurrentUser = async () => {
    const response = await api.get("/auth/me");
    return response.data;
};