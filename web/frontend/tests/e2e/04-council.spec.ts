/**
 * Ratsinformationssystem: search, scope tabs, session detail dialog.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

const MOCK_SESSION = {
  ksinr: 42,
  committee: "Bauausschuss",
  session_date: "2026-07-15",
  session_time: "18:00",
  location: "Rathaus, Saal A",
  n_items: 3,
};

const MOCK_DETAIL = {
  ...MOCK_SESSION,
  agenda_items: [
    { item_number: "Ö 1", title: "Bebauungsplan Hafen", vorlage_nr: "2026/123", kvonr: null, is_public: 1 },
    { item_number: "Ö 2", title: "Radwegekonzept", vorlage_nr: null, kvonr: null, is_public: 1 },
    { item_number: "N 1", title: "Personalangelegenheit", vorlage_nr: null, kvonr: null, is_public: 0 },
  ],
  url: "https://ratsinfo.oldenburg.de/ksinr=42",
};

test.describe("Ratsinformationssystem", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);

    await page.route("**/api/council/committees", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ committees: ["Bauausschuss", "Stadtentwicklungsausschuss"] }),
      }),
    );
    await page.route("**/api/council/sessions**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ sessions: [MOCK_SESSION], count: 1 }),
      }),
    );
  });

  test("shows page header and scope tabs", async ({ page }) => {
    await page.goto("/council");
    await expect(page.getByRole("heading", { name: "Ratsinformationssystem" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Kommend" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Vergangen" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Alle" })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/04-council-page.png", fullPage: true });
  });

  test("shows session cards loaded from backend", async ({ page }) => {
    await page.goto("/council");
    await expect(page.getByText("Bauausschuss")).toBeVisible();
    await expect(page.getByText(/15\. Juli 2026|2026-07-15/)).toBeVisible();
    await expect(page.getByText("3 TOP")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/04-council-sessions.png", fullPage: true });
  });

  test("clicking a session opens the detail dialog", async ({ page }) => {
    await page.route("**/api/council/session/42", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_DETAIL) }),
    );

    await page.goto("/council");
    await page.getByText("Bauausschuss").click();
    // Dialog should open with agenda items
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Bebauungsplan Hafen")).toBeVisible();
    await expect(page.getByText("nichtöffentlich")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/04-council-detail.png", fullPage: true });
  });

  test("scope tab change triggers reload", async ({ page }) => {
    let callCount = 0;
    await page.route("**/api/council/sessions**", (route) => {
      callCount++;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [], count: 0 }) });
    });

    await page.goto("/council");
    await page.getByRole("button", { name: "Vergangen" }).click();
    await page.waitForTimeout(500);
    expect(callCount).toBeGreaterThanOrEqual(2);
    await page.screenshot({ path: "test-results/screenshots/04-council-scope-switch.png", fullPage: true });
  });
});
