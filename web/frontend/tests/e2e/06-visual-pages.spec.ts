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
  { name: "bookmarks", path: "/bookmarks", auth: true },
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
        await page.route("**/api/bookmarks", (r) =>
          r.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ bookmarks: pg.name === "bookmarks" ? [
              {
                id: 1, kind: "agenda_item", target_key: "agenda_item:42:2026/123",
                title: "Sichere Radwege an der Alexanderstraße", subtitle: "Bauausschuss · 2026-09-08 · Ö 2",
                created_at: "2026-08-26T12:00:00", notify_result: true,
                result_notified_at: null, state: "upcoming",
                url: "/council?tab=sessions&ksinr=42&top=%C3%96%202", ksinr: 42,
                item_number: "Ö 2", decision: null,
                agenda_item: { item_number: "Ö 2", title: "Sichere Radwege an der Alexanderstraße", vorlage_nr: "2026/123", kvonr: 123, is_public: 1 },
                session: { ksinr: 42, committee: "Bauausschuss", session_date: "2026-09-08", session_time: "17:00", location: "Rathaus", n_items: 3 },
              },
            ] : [] }),
          }),
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
