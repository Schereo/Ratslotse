/**
 * Visual smoke test: screenshot every main page at desktop + mobile viewport.
 * No assertions beyond "page loads without crashing" — the screenshots are the
 * deliverable, viewable in the HTML report.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

const BAU = { ksinr: 42, committee: "Bauausschuss", session_date: "2026-08-20", session_time: "17:00", location: "Rathaus", n_items: 9 };
const RAT = { ksinr: 43, committee: "Rat", session_date: "2026-08-31", session_time: "18:00", location: "Weser-Ems-Hallen", n_items: 15 };
const BOOKMARKS = [
  {
    id: 1, kind: "agenda_item", target_key: "agenda_item:42:2026/123",
    title: "Sichere Radwege an der Alexanderstraße und zusätzliche Querungshilfen an mehreren Kreuzungen", subtitle: "Bauausschuss · 2026-08-20 · Ö 2",
    created_at: "2026-08-26T12:00:00", notify_result: true,
    result_notified_at: null, state: "waiting", is_group: false,
    url: "/council?tab=sessions&ksinr=42&top=%C3%96%202", ksinr: 42,
    item_number: "Ö 2", decision: null,
    agenda_item: { item_number: "Ö 2", title: "Sichere Radwege an der Alexanderstraße und zusätzliche Querungshilfen an mehreren Kreuzungen", vorlage_nr: "2026/123", kvonr: 123, is_public: 1 },
    session: BAU,
  },
  {
    id: 2, kind: "agenda_item", target_key: "agenda_item:42:2026/124",
    title: "Neue Fahrradständer am Bahnhof", subtitle: "Bauausschuss · 2026-08-20 · Ö 3",
    created_at: "2026-08-26T12:01:00", notify_result: false,
    result_notified_at: null, state: "waiting", is_group: false,
    url: "/council?tab=sessions&ksinr=42&top=%C3%96%203", ksinr: 42,
    item_number: "Ö 3", decision: null,
    agenda_item: { item_number: "Ö 3", title: "Neue Fahrradständer am Bahnhof", vorlage_nr: "2026/124", kvonr: 124, is_public: 1 },
    session: BAU,
  },
  {
    id: 3, kind: "decision", target_key: "decision:42:4",
    title: "Bebauungsplan am Hafen", subtitle: "Bauausschuss · 2026-08-20 · Ö 4",
    created_at: "2026-08-26T12:02:00", notify_result: false,
    result_notified_at: null, state: "decided", is_group: false,
    url: "/council/decision?id=91", ksinr: 42, item_number: "Ö 4",
    agenda_item: null, session: BAU,
    decision: { id: 91, outcome: "accepted", title: "Bebauungsplan am Hafen", simple_summary: "Der Bebauungsplan wurde beschlossen." },
  },
  ...[5, 6, 7].map((number, index) => ({
    id: number, kind: "agenda_item", target_key: `agenda_item:43:${number}`,
    title: ["VBN-Tarifanpassung 2027", "Änderung der Satzung des Jugendamtes", "Mitteilungen des Oberbürgermeisters"][index],
    subtitle: `Rat · 2026-08-31 · Ö ${number}`,
    created_at: `2026-08-26T12:0${number}:00`, notify_result: false,
    result_notified_at: null, state: "upcoming", is_group: false,
    url: `/council?tab=sessions&ksinr=43&top=%C3%96%20${number}`, ksinr: 43,
    item_number: `Ö ${number}`, decision: null,
    agenda_item: { item_number: `Ö ${number}`, title: "Anstehender Rats-TOP", vorlage_nr: null, kvonr: null, is_public: 1 },
    session: RAT,
  })),
  {
    id: 9, kind: "session", target_key: "session:44", title: "Sozialausschuss",
    subtitle: "Sozialausschuss · 2026-09-08", created_at: "2026-08-26T12:09:00",
    notify_result: false, result_notified_at: null, state: "upcoming", is_group: false,
    url: "/council?tab=sessions&ksinr=44", ksinr: 44, item_number: null,
    agenda_item: null, decision: null,
    session: { ksinr: 44, committee: "Sozialausschuss", session_date: "2026-09-08", session_time: "17:00", location: "PFL", n_items: 8 },
  },
];

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
            body: JSON.stringify({ bookmarks: pg.name === "bookmarks" ? BOOKMARKS : [] }),
          }),
        );

        if (pg.auth) {
          await loginAdmin(page);
        }
        await page.goto(pg.path, { waitUntil: "networkidle" });
        // Just assert the page doesn't show a fatal error
        await expect(page.locator("body")).not.toContainText("Application error");
        if (pg.name === "bookmarks") {
          await expect(page.getByLabel(/Bauausschuss.*3 Einträge anzeigen/)).toBeVisible();
          await expect(page.getByText(/Sichere Radwege an der Alexanderstraße/)).toBeHidden();
        }
        await page.screenshot({
          path: `test-results/screenshots/06-${vp.name}-${pg.name}.png`,
          fullPage: true,
        });
        if (pg.name === "bookmarks") {
          await page.getByLabel(/Bauausschuss.*3 Einträge anzeigen/).click();
          await expect(page.getByText(/Sichere Radwege an der Alexanderstraße/)).toBeVisible();
          if (vp.name === "desktop") {
            const notificationBottoms = await page.locator("[data-notification-row]").evaluateAll((rows) => (
              rows.map((row) => row.getBoundingClientRect().bottom)
            ));
            expect(notificationBottoms).toHaveLength(2);
            expect(Math.abs(notificationBottoms[0] - notificationBottoms[1])).toBeLessThanOrEqual(1);
          }
          await page.screenshot({
            path: `test-results/screenshots/06-${vp.name}-${pg.name}-expanded.png`,
            fullPage: true,
          });
          await page.getByRole("button", { name: /Entschieden 1/ }).click();
          await expect(page.getByText("1 gemerkter Eintrag")).toBeVisible();
        }
      });
    }
  });
}
