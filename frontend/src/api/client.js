import axios from "axios";

export const API_BASE_URL =
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const TOKEN_STORAGE_KEY = "crypto_bot_api_token";

export function getToken() {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
}

export function setToken(token) {
    if (token) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
}

export function clearToken() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
}

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

api.interceptors.request.use((config) => {
    const token = getToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default api;
