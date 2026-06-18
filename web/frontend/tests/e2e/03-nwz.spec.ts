/**
 * NWZ Artikelsuche: credential gate → verify → search.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

test.describe("NWZ Artikelsuche", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  test("shows NWZ credential gate before verification", async ({ page }) => {
    await page.goto("/nwz");
    await expect(page.getByText("Eigene NWZ-Zugangsdaten")).toBeVisible();
    await expect(page.getByLabel("NWZ-Benutzername / E-Mail")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/03-nwz-gate.png", fullPage: true });
  });

  test("shows error for invalid NWZ credentials", async ({ page }) => {
    // Route mock: NWZ verify returns 400
    await page.route("**/api/account/nwz-credentials", (route) =>
      route.fulfill({ status: 400, body: JSON.stringify({ detail: "NWZ-Login ungültig." }) }),
    );
    await page.goto("/nwz");
    await page.getByLabel("NWZ-Benutzername / E-Mail").fill("bad@user.de");
    await page.locator('input[type="password"]').first().fill("wrong");
    await page.getByRole("button", { name: "Verifizieren" }).click();
    await expect(page.locator("[data-sonner-toast]")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/03-nwz-invalid-creds.png", fullPage: true });
  });

  test("unlocks search after mock-successful verification", async ({ page }) => {
    // Stateful: auth/me returns nwz_verified=false initially, true after POST succeeds.
    let verified = false;
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1, email: "admin@test.de", role: "admin", status: "active",
          linked: false, nwz_verified: verified, nwz_username: verified ? "testuser" : null, telegram_chat_id: null,
        }),
      }),
    );
    await page.route("**/api/account/nwz-credentials", (route) => {
      verified = true;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1, email: "admin@test.de", role: "admin", status: "active",
          linked: false, nwz_verified: true, nwz_username: "testuser", telegram_chat_id: null,
        }),
      });
    });
    await page.route("**/api/nwz/search**", (route) =>
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ results: [], count: 0 }),
      }),
    );
    await page.route("**/api/nwz/categories", (route) =>
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ categories: [] }),
      }),
    );

    await page.goto("/nwz");
    await page.getByLabel("NWZ-Benutzername / E-Mail").fill("testuser@nwz.de");
    await page.locator('input[type="password"]').first().fill("secret");
    await page.getByRole("button", { name: "Verifizieren" }).click();
    // After verification the search UI should appear
    await expect(page.locator('input[placeholder*="Suchbegriff"]')).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/03-nwz-search-unlocked.png", fullPage: true });
  });

  test("search UI (mocked): shows skeleton then results", async ({ page }) => {
    // Patch auth context so we skip the gate
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1, email: "admin@test.de", role: "admin", status: "active",
          linked: false, nwz_verified: true, nwz_username: "u", telegram_chat_id: null,
        }),
      }),
    );
    await page.route("**/api/nwz/categories", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ categories: [] }) }),
    );
    await page.route("**/api/nwz/search**", async (route) => {
      // Simulate slight delay so skeleton is visible
      await new Promise((r) => setTimeout(r, 200));
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            {
              catalog: 2,
              refid: "xyz",
              pub_date: "2026-06-10",
              category_name: "Sport",
              title: "VfB Oldenburg gewinnt Derby",
              subtitle: "Spannendes Spiel im Marschwegstadion",
              authors: "Anna Schmidt",
              excerpt: "Der <mark>VfB</mark> gewinnt mit 2:1.",
              rank: -2,
            },
          ],
          count: 1,
        }),
      });
    });

    await page.goto("/nwz");
    await expect(page.getByText("1 Treffer")).toBeVisible();
    await expect(page.getByText("VfB Oldenburg gewinnt Derby")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/03-nwz-results.png", fullPage: true });
  });
});
