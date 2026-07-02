/**
 * Topics & Subscriptions: add/delete topic, confirm dialog, empty state.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

function mockUser(page: import("@playwright/test").Page) {
  return page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1, email: "admin@test.de", role: "admin", status: "active",
        email_verified: true, delivery_channel: "email",
      }),
    }),
  );
}

test.describe("Topics", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  test("shows empty state with CTA when no topics", async ({ page }) => {
    await page.route("**/api/topics", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
    );
    await page.route("**/api/subscriptions", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: [] }) }),
    );
    await page.route("**/api/council/committees", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: [] }) }),
    );

    await page.goto("/topics");
    await expect(page.getByText("Noch keine Themen")).toBeVisible();
    await expect(page.getByRole("button", { name: /Erstes Thema anlegen/ })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/05-topics-empty.png", fullPage: true });
  });

  test("CTA in empty state focuses the name input", async ({ page }) => {
    await mockUser(page);
    await page.route("**/api/topics", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
    );
    await page.route("**/api/subscriptions", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: [] }) }),
    );
    await page.route("**/api/council/committees", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: [] }) }),
    );

    await page.goto("/topics");
    await page.getByRole("button", { name: /Erstes Thema anlegen/ }).click();
    // Name input should be focused
    const nameInput = page.locator('input[placeholder*="Radwege"]');
    await expect(nameInput).toBeFocused();
  });

  test("shows topic list with match count badge", async ({ page }) => {
    await mockUser(page);
    await page.route("**/api/topics", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: 1, name: "Radwege", description: "Ausbau in Oldenburg", created_at: "2026-06-01", match_count: 7 },
          { id: 2, name: "Stadtpark", description: "Neue Grünflächen", created_at: "2026-06-02", match_count: 0 },
        ]),
      }),
    );
    await page.route("**/api/subscriptions", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: ["Bauausschuss"] }) }),
    );
    await page.route("**/api/council/committees", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: ["Bauausschuss"] }) }),
    );

    await page.goto("/topics");
    await expect(page.getByText("Radwege")).toBeVisible();
    await expect(page.getByText("7 Treffer")).toBeVisible();
    await expect(page.getByText("Stadtpark")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/05-topics-list.png", fullPage: true });
  });

  test("delete opens confirm dialog, not window.confirm", async ({ page }) => {
    await mockUser(page);
    await page.route("**/api/topics", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: 1, name: "Radwege", description: "Ausbau", created_at: "2026-06-01", match_count: 3 },
        ]),
      }),
    );
    await page.route("**/api/subscriptions", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: [] }) }),
    );
    await page.route("**/api/council/committees", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: [] }) }),
    );

    await page.goto("/topics");
    // Click the trash icon — should open a custom dialog, NOT window.confirm
    await page.locator('[aria-label*="Löschen"], button:has([data-lucide="trash-2"])').first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Thema löschen")).toBeVisible();
    // animations: "disabled" fast-forwards the dialog fade so the capture isn't
    // taken mid-animation (which renders the content semi-transparent).
    await page.screenshot({ path: "test-results/screenshots/05-topics-confirm-dialog.png", fullPage: true, animations: "disabled" });
  });
});
