// Native push notifications (Capacitor). No-ops on the web.
//
// Split in two: initPush() wires the OS listeners once (device token → backend,
// notification tap → in-app navigation) and is called from the app shell after
// login; enablePush() prompts for permission and is called when the user picks
// the Push delivery channel. @capacitor/push-notifications is dynamically
// imported so it never enters the web bundle's critical path.
import { isNativeApp, nativePlatform } from "./platform";
import { api } from "./api";

let initialized = false;
// The OS-issued device token, kept so logout can unregister it server-side.
let deviceToken: string | null = null;

async function postToken(value: string): Promise<void> {
  deviceToken = value;
  try {
    await api.post("/push/register", { token: value, platform: nativePlatform() ?? "ios" });
  } catch {
    /* best-effort — the app re-registers on the next launch */
  }
}

/** Wire push listeners once: registration → backend, tap → navigate. Safe on web. */
export async function initPush(navigate: (path: string) => void): Promise<void> {
  if (!isNativeApp() || initialized) return;
  initialized = true;
  const { PushNotifications } = await import("@capacitor/push-notifications");
  await PushNotifications.addListener("registration", (t) => { void postToken(t.value); });
  await PushNotifications.addListener("registrationError", () => { /* ignore; retry next launch */ });
  await PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
    const url = action.notification?.data?.url;
    if (typeof url === "string" && url.startsWith("/")) navigate(url);
  });
  // Already granted on a previous launch? Refresh the token silently.
  const perm = await PushNotifications.checkPermissions();
  if (perm.receive === "granted") await PushNotifications.register();
}

/** Drop this device's token server-side — called on logout while the session is
 *  still valid, so the device stops receiving the old account's notifications.
 *  The OS permission stays granted; the next login re-registers. No-op on web. */
export async function unregisterPush(): Promise<void> {
  if (!isNativeApp() || !deviceToken) return;
  try {
    await api.post("/push/unregister", { token: deviceToken });
  } catch {
    /* offline is fine — a later login re-homes the token to its account */
  }
}

/** Prompt for notification permission and register this device.
 *  Returns true if granted (the token then flows to the initPush listener). */
export async function enablePush(): Promise<boolean> {
  if (!isNativeApp()) return false;
  const { PushNotifications } = await import("@capacitor/push-notifications");
  let perm = await PushNotifications.checkPermissions();
  if (perm.receive !== "granted") perm = await PushNotifications.requestPermissions();
  if (perm.receive !== "granted") return false;
  await PushNotifications.register();
  return true;
}
