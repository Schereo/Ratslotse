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
          { id: 1, name: "Radwege", description: "Ausbau in Oldenburg", created_at: "2026-06-01", decision_count: 7 },
          { id: 2, name: "Stadtpark", description: "Neue Grünflächen", created_at: "2026-06-02", decision_count: 0 },
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
    await expect(page.getByText("7 Beschlüsse")).toBeVisible();
    await expect(page.getByText("Stadtpark")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/05-topics-list.png", fullPage: true });
  });

  test("die Lösch-Rückfrage steht in der Karte, nicht in window.confirm", async ({ page }) => {
    await mockUser(page);
    await page.route("**/api/topics", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: 1, name: "Radwege", description: "Ausbau", created_at: "2026-06-01", decision_count: 3 },
        ]),
      }),
    );
    await page.route("**/api/subscriptions", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscriptions: [] }) }),
    );
    await page.route("**/api/council/committees", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ committees: [] }) }),
    );

    // Ein echtes `window.confirm` würde Playwright automatisch wegklicken —
    // deshalb wird hier mitgeschrieben, ob überhaupt eines auftaucht.
    const browserDialoge: string[] = [];
    page.on("dialog", (d) => { browserDialoge.push(d.type()); void d.dismiss(); });

    await page.goto("/topics");
    // Der Knopf trägt den Themennamen in seiner Beschriftung („Radwege
    // löschen") — klein geschrieben. Der alte Selektor suchte nach
    // `aria-label*="Löschen"` mit großem L und fand nichts.
    await page.getByRole("button", { name: "Radwege löschen" }).click();
    // Der Punkt dieses Tests ist unverändert: Es darf KEIN `window.confirm`
    // sein. Nur steht die Rückfrage seit dem Umbau in der Karte selbst und
    // nicht mehr in einem Dialog darüber.
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText(/Thema löschen\? Du bekommst dazu keine Treffer mehr\./)).toBeVisible();
    expect(browserDialoge, "window.confirm hätte den Test blockiert").toEqual([]);
    // animations: "disabled" fast-forwards the dialog fade so the capture isn't
    // taken mid-animation (which renders the content semi-transparent).
    await page.screenshot({ path: "test-results/screenshots/05-topics-confirm-dialog.png", fullPage: true, animations: "disabled" });
  });
});
