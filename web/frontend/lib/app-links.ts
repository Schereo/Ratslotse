// Universal Links (iOS) / App Links (Android): open ratslotse.de deep links —
// e.g. the email verify/reset links — inside the app instead of the browser.
// No-op on the web. Wired globally in providers.tsx so it also covers the public
// /verify-email and /reset-password routes (outside the authed (app) area).
import { isNativeApp } from "./platform";

let done = false;

/** Map web-only dynamic routes to their static-app query equivalents. */
export function appRoute(pathname: string, search: string): string {
  const problem = pathname.match(/^\/probleme\/([1-9]\d*)$/);
  if (problem) return `/probleme?problem=${problem[1]}`;
  return pathname + search;
}

export async function initAppUrlOpen(navigate: (path: string) => void): Promise<void> {
  if (!isNativeApp() || done) return;
  done = true;
  const { App } = await import("@capacitor/app");
  await App.addListener("appUrlOpen", ({ url }) => {
    try {
      const u = new URL(url);
      navigate(appRoute(u.pathname, u.search)); // strip the origin → in-app route
    } catch {
      /* ignore malformed URLs */
    }
  });
}
