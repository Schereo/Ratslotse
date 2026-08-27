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
    // h3 is inside a <button> — Chrome suppresses its heading role, use CSS tag selector
    await expect(page.locator("main h3", { hasText: "Bauausschuss" })).toBeVisible();
    await expect(page.getByText(/15\.07\.2026/)).toBeVisible(); // formatDate returns dd.mm.yyyy
    await expect(page.getByText("3 TOP")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/04-council-sessions.png", fullPage: true });
  });

  test("clicking a session opens the detail dialog", async ({ page }) => {
    await page.route("**/api/council/session/42", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_DETAIL) }),
    );

    await page.goto("/council");
    // Click the card (button) that contains the h3 — target the outer button
    await page.locator("main button", { hasText: "Bauausschuss" }).first().click();
    // Dialog should open with agenda items
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Bebauungsplan Hafen")).toBeVisible();
    await expect(page.getByText("nichtöffentlich")).toBeVisible();
    // animations: "disabled" fast-forwards the dialog fade/zoom so the capture
    // isn't taken mid-animation (which renders the content semi-transparent).
    await page.screenshot({ path: "test-results/screenshots/04-council-detail.png", fullPage: true, animations: "disabled" });
  });

  test("only concrete subitems offer a bookmark button", async ({ page }) => {
    await page.route("**/api/council/session/42", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...MOCK_DETAIL,
          agenda_items: [
            { item_number: "Ö 4", title: "Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder", vorlage_nr: null, kvonr: null, is_public: 1 },
            { item_number: "Ö 4.1", title: "Antrag: Mehr sichere Schulwege", vorlage_nr: "2026/401", kvonr: 401, is_public: 1 },
          ],
        }),
      }),
    );

    await page.goto("/council?tab=sessions");
    await page.locator("main button", { hasText: "Bauausschuss" }).first().click();
    const parent = page.locator("li", { hasText: "Anträge der Fraktionen" });
    const child = page.locator("li", { hasText: "Mehr sichere Schulwege" });
    await expect(parent.getByRole("button", { name: "Zur Merkliste hinzufügen" })).toHaveCount(0);
    await expect(child.getByRole("button", { name: "Zur Merkliste hinzufügen" })).toBeVisible();
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

  test("filters decisions by location and shows the evidence", async ({ page }) => {
    await page.route("**/api/council/fields", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ fields: [] }) }),
    );
    await page.route("**/api/council/districts", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          districts: [{ name: "Kreyenbrück", count: 2, vote_count: 1, report_count: 1 }],
        }),
      }),
    );
    let requestedDistrict = "";
    await page.route("**/api/council/decisions**", (route) => {
      requestedDistrict = new URL(route.request().url()).searchParams.get("district") ?? "";
      const decision = {
        id: 11, ksinr: 42, kind: "decision", parent_item: null, item_number: "5",
        title: "Widmung Klingenbergplatz", beschluss: "Die Erweiterungsfläche wird gewidmet.",
        outcome: "angenommen", vote: null, gegenstimmen: null, enthaltungen: null,
        factions: [], parties: [], vorlage_nr: null, raw_result: null,
        committee: "Bauausschuss", session_date: "2026-07-15", protocol_url: null,
        policy_field: null, policy_tags: [], summary: null, amount_eur: null,
        location_matches: requestedDistrict ? [{
          name: "Klingenbergplatz", stadtteil: "Kreyenbrück", source: "title",
          evidence: "Widmung Klingenbergplatz", method: "regex", confidence: 0.98,
        }] : [],
      };
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ total: 1, decisions: [decision] }),
      });
    });

    await page.goto("/council?tab=decisions");
    await page.getByRole("button", { name: "Ortsbezug" }).click();
    await page.getByRole("button", { name: "Kreyenbrück (1)" }).click();

    await expect.poll(() => requestedDistrict).toBe("Kreyenbrück");
    await expect(page).toHaveURL(/district=Kreyenbr%C3%BCck/);
    await expect(page.getByText("Ortsbezug:", { exact: true })).toBeVisible();
    await expect(page.getByText("Fundstelle: „Widmung Klingenbergplatz“")).toBeVisible();
  });
});
