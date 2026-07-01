// Bearer-token storage for the native app.
//
// The web build authenticates via the httpOnly session cookie and never stores a
// token here (getCachedToken() stays null), so the browser never exposes a token
// to page JS. The native app can't rely on cross-site cookies, so it keeps the
// JWT in secure device storage (Capacitor Preferences) and sends it as a bearer.
import { Preferences } from "@capacitor/preferences";
import { isNativeApp } from "./platform";

const KEY = "access_token";
let cached: string | null = null;

/** Hydrate the in-memory token from device storage once, at app start. */
export async function loadToken(): Promise<string | null> {
  if (!isNativeApp()) return null;
  try {
    const { value } = await Preferences.get({ key: KEY });
    cached = value ?? null;
  } catch {
    cached = null;
  }
  return cached;
}

/** Synchronous accessor the api client uses to set the Authorization header. */
export function getCachedToken(): string | null {
  return cached;
}

/** Persist (or clear) the token after login/logout. No-op on the web. */
export async function setToken(token: string | null): Promise<void> {
  cached = token;
  if (!isNativeApp()) return;
  try {
    if (token) await Preferences.set({ key: KEY, value: token });
    else await Preferences.remove({ key: KEY });
  } catch {
    /* ignore storage errors — worst case the user re-authenticates */
  }
}
