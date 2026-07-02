// Thin fetch wrapper around the /api backend.
// On the web this is same-origin and auth rides in the httpOnly cookie. In the
// native app the base is the absolute backend origin and auth is a bearer token.
import { toast } from "sonner";
import { apiBase, isNativeApp } from "./platform";
import { getCachedToken } from "./token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Global handler invoked when a session expires mid-use (401 on a non-auth
// endpoint). The AuthProvider registers it to clear state and redirect.
let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const native = isNativeApp();
  const token = native ? getCachedToken() : null;
  const res = await fetch(`${apiBase()}/api${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      // The native app has no cross-site cookie: it flags itself so the backend
      // returns a long-lived token on login, and carries that token as a bearer.
      ...(native ? { "X-Client": "app" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    toast.info("Sitzung abgelaufen – bitte melde dich erneut an.");
    unauthorizedHandler?.();
  }

  if (!res.ok) {
    let detail = `Fehler ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
};

/** Absolute URL for a backend path: same-origin on web, absolute in the native app. */
export function apiUrl(path: string): string {
  return `${apiBase()}/api${path}`;
}

/** Auth headers for manual fetches (e.g. SSE streaming) that bypass the `api` wrapper.
 *  Empty on web (the cookie handles auth); bearer + client marker in the app. */
export function authHeaders(): Record<string, string> {
  const native = isNativeApp();
  const token = native ? getCachedToken() : null;
  return {
    ...(native ? { "X-Client": "app" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}
