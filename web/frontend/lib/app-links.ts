// Universal Links (iOS) / App Links (Android): open ratslotse.de deep links —
// e.g. the email verify/reset links — inside the app instead of the browser.
// No-op on the web. Wired globally in providers.tsx so it also covers the public
// /verify-email and /reset-password routes (outside the authed (app) area).
import { isNativeApp } from "./platform";
import { parseProblemId, problemAppDetailHref } from "./probleme";

let done = false;

/** Web-only dynamic routes auf ihre statisch exportierbare App-Form abbilden. */
export function appRoute(pathname: string, search: string): string {
  const match = pathname.match(/^\/probleme\/(-?\d+)\/?$/);
  if (!match) return pathname + search;
  const problemId = parseProblemId(match[1]);
  return problemId === null
    ? `/probleme?problem=${encodeURIComponent(match[1])}`
    : problemAppDetailHref(problemId);
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
