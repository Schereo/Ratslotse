/**
 * Visual smoke test: screenshot every main page at desktop + mobile viewport.
 * No assertions beyond "page loads without crashing" — the screenshots are the
 * deliverable, viewable in the HTML report.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

const PAGES = [
  { name: "login", path: "/login", auth: false },
  { name: "register", path: "/register", auth: false },
  { name: "dashboard", path: "/dashboard", auth: true },
  { name: "council", path: "/council", auth: true },
  { name: "topics", path: "/topics", auth: true },
  { name: "account", path: "/account", auth: true },
];

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

for (const vp of VIEWPORTS) {
  test.describe(`Visual smoke — ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    // Mock the authenticated endpoints for pages that need auth
    for (const pg of PAGES) {
      test(`${pg.name} renders without error`, async ({ page }) => {
        // Mock slow/unavailable APIs so page at least paints
        await page.route("**/api/council/sessions**", (r) =>
          r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [], count: 0 }) }),
        );
        await page.route("**/api/council/committees", (r) =>
          r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: [] }) }),
        );
        await page.route("**/api/topics", (r) =>
          r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
        );
        await page.route("**/api/subscriptions", (r) =>
          r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: [] }) }),
        );

        if (pg.auth) {
          await loginAdmin(page);
        }
        await page.goto(pg.path, { waitUntil: "networkidle" });
        // Just assert the page doesn't show a fatal error
        await expect(page.locator("body")).not.toContainText("Application error");
        await page.screenshot({
          path: `test-results/screenshots/06-${vp.name}-${pg.name}.png`,
          fullPage: true,
        });
      });
    }
  });
}
