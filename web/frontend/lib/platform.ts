// Runtime detection (native Capacitor shell vs browser) and API base resolution.
//
// On the web the app is served same-origin, so the base is "" and requests go to
// /api (proxied to the backend by next.config / Caddy). Inside the native app the
// same bundle is loaded from capacitor://localhost, so requests must target the
// absolute backend origin instead.
import { Capacitor } from "@capacitor/core";

export function isNativeApp(): boolean {
  try {
    return Capacitor.isNativePlatform();
  } catch {
    return false;
  }
}

export function nativePlatform(): "ios" | "android" | null {
  try {
    const p = Capacitor.getPlatform();
    return p === "ios" || p === "android" ? p : null;
  } catch {
    return null;
  }
}

// Absolute backend origin for the native app; "" (same-origin) on the web.
export function apiBase(): string {
  if (!isNativeApp()) return "";
  return process.env.NEXT_PUBLIC_API_BASE || "https://ratslotse.de";
}
