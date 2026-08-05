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

/** Wire push listeners (once) und dieses Gerät anmelden (bei JEDER Anmeldung).
 *
 *  Die Trennung ist der Punkt: Die Zuhörer dürfen nur einmal gesetzt werden —
 *  zweimal, und jeder Tap würde doppelt navigieren. Das `register()` muss
 *  dagegen bei jeder Anmeldung laufen.
 *
 *  Vorher stand ein `initialized`-Riegel vor der ganzen Funktion. Er gilt für
 *  die gesamte App-Sitzung, und `logout()` löscht das Token serverseitig
 *  (`unregisterPush`). Wer sich also ab- und wieder anmeldete, ohne die App
 *  zwischendurch ganz zu beenden, stand danach **ohne Token** da: Push war
 *  still tot, bis zum nächsten vollständigen App-Start. Der Kommentar
 *  versprach „the next login re-registers" — genau das tat es nicht.
 */
export async function initPush(navigate: (path: string) => void): Promise<void> {
  if (!isNativeApp()) return;
  const { PushNotifications } = await import("@capacitor/push-notifications");
  if (!initialized) {
    initialized = true;
    await PushNotifications.addListener("registration", (t) => { void postToken(t.value); });
    await PushNotifications.addListener("registrationError", () => { /* ignore; retry next launch */ });
    await PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
      const url = action.notification?.data?.url;
      if (typeof url === "string" && url.startsWith("/")) navigate(url);
    });
  }
  // Erlaubnis liegt schon vor? Dann das Token (neu) holen — iOS liefert es
  // erneut an den `registration`-Zuhörer, der es beim Backend anmeldet.
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
  } finally {
    // Serverseitig ist das Token weg; es hier stehen zu lassen hieße, beim
    // nächsten Abmelden ein fremdes oder totes Token abzumelden. Die nächste
    // Anmeldung holt es über `initPush` ohnehin frisch.
    deviceToken = null;
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
