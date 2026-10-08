// Universal Links (iOS) / App Links (Android): open ratslotse.de deep links —
// e.g. the email verify/reset links — inside the app instead of the browser.
// No-op on the web. Wired globally in providers.tsx so it also covers the public
// /verify-email and /reset-password routes (outside the authed (app) area).
import { isNativeApp } from "./platform";
import { sicheresZiel } from "./public-routes";

let done = false;

/** Hosts, deren Links die App öffnen darf (die verknüpften Domains). */
const APP_HOSTS = new Set(["ratslotse.de", "www.ratslotse.de"]);

/** Aus einer geöffneten Adresse den In-App-Pfad machen — oder `null`.
 *
 *  Die Adresse kommt von außen: Auf Android kann jede andere App einen
 *  Intent an die Hülle schicken. Bis 10/2026 ging deren `pathname` ungeprüft
 *  an den Router; bei `x:javascript:…` IST der Pfad `javascript:…`, und der
 *  Router führte ihn als Skript aus (F12). Deshalb nur https auf unseren
 *  Hosts, und der Pfad muss dieselbe Prüfung bestehen wie jedes
 *  Rücksprungziel. */
export function appPfad(url: string): string | null {
  try {
    const u = new URL(url);
    if (u.protocol !== "https:" || !APP_HOSTS.has(u.hostname)) return null;
    return sicheresZiel(u.pathname + u.search);
  } catch {
    return null;
  }
}

export async function initAppUrlOpen(navigate: (path: string) => void): Promise<void> {
  if (!isNativeApp() || done) return;
  done = true;
  const { App } = await import("@capacitor/app");
  await App.addListener("appUrlOpen", ({ url }) => {
    const pfad = appPfad(url);
    if (pfad) navigate(pfad); // strip the origin → in-app route
  });
}
