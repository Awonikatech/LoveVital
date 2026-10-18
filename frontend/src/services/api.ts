import axios, { AxiosError, type AxiosRequestConfig } from "axios";
import type { ApiErrorBody, TokenResponse } from "@/types";

/**
 * Session strategy
 *  - Access token (15 min JWT) lives only in memory.
 *  - Refresh token lives in an HttpOnly cookie scoped to /api/v1/auth (JS can't read it).
 *  - Refresh/logout send the double-submit CSRF token from the readable `swk_csrf` cookie.
 *  - Guests are identified by an opaque cart token kept in localStorage (no personal data).
 */
let accessToken: string | null = null;
let refreshing: Promise<TokenResponse | null> | null = null;
const listeners = new Set<(t: TokenResponse | null) => void>();

const CART_KEY = "swk_cart_token";

export const api = axios.create({ baseURL: "/api/v1", withCredentials: true, timeout: 20000 });

export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}
export function onSessionChange(fn: (t: TokenResponse | null) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getCartToken(): string | null {
  try {
    return localStorage.getItem(CART_KEY);
  } catch {
    return null;
  }
}
export function setCartToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CART_KEY, token);
    else localStorage.removeItem(CART_KEY);
  } catch {
    /* storage unavailable (private mode) — cart still works for this tab via memory */
  }
}

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}

export function csrfHeaders() {
  const t = readCookie("swk_csrf");
  return t ? { "X-CSRF-Token": t } : {};
}

api.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  if (accessToken) config.headers["Authorization"] = `Bearer ${accessToken}`;
  const cart = getCartToken();
  if (cart) config.headers["X-Cart-Token"] = cart;
  return config;
});

export async function refreshSession(): Promise<TokenResponse | null> {
  if (!readCookie("swk_csrf")) return null; // never logged in on this browser
  if (!refreshing) {
    refreshing = axios
      .post<TokenResponse>("/api/v1/auth/refresh", null, { withCredentials: true, headers: csrfHeaders() })
      .then((r) => {
        setAccessToken(r.data.access_token);
        listeners.forEach((l) => l(r.data));
        return r.data;
      })
      .catch(() => {
        setAccessToken(null);
        listeners.forEach((l) => l(null));
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    const code = error.response?.data?.error?.code;
    if (error.response?.status === 401 && original && !original._retried && (code === "token_expired" || code === "invalid_token")) {
      original._retried = true;
      const t = await refreshSession();
      if (t) return api(original);
    }
    return Promise.reject(error);
  },
);

export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body?.error?.message) return body.error.message;
    if (err.code === "ECONNABORTED") return "The request timed out. Check your connection and try again.";
    if (!err.response) return "Can't reach the store right now. Check your connection.";
  }
  return fallback;
}

export function errorCode(err: unknown): string | undefined {
  return axios.isAxiosError(err) ? (err.response?.data as ApiErrorBody | undefined)?.error?.code : undefined;
}

export async function downloadFile(url: string, filename: string) {
  const r = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
