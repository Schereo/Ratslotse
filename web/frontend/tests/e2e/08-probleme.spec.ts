import { expect, test } from "@playwright/test";

const problems = [
  {
    id: 1, title: "Beispiel: dunkler Fußweg", category: "public_space",
    scope_kind: "point", location_label: "Fiktiver Beispielort",
    latitude: 53.14, longitude: 8.21, geometry: null,
    status: "multiple_reports", frequency: "several", fictional: true,
  },
  {
    id: 2, title: "Beispiel: Musterhalle", category: "mobility",
    scope_kind: "facility", location_label: "Fiktive Musterhalle",
    latitude: 53.145, longitude: 8.22, geometry: null,
    status: "verified", frequency: "very_many", fictional: true,
  },
  {
    id: 3, title: "Beispiel: Radroute", category: "mobility",
    scope_kind: "route", location_label: "Fiktive Beispielroute",
    latitude: null, longitude: null,
    geometry: { type: "LineString", coordinates: [[8.19, 53.14], [8.22, 53.15]] },
    status: "new", frequency: "once", fictional: true,
  },
  {
    id: 4, title: "Beispiel: Musterquartier", category: "environment",
    scope_kind: "area", location_label: "Fiktives Musterquartier",
    latitude: null, longitude: null,
    geometry: { type: "Polygon", coordinates: [[[8.2, 53.13], [8.22, 53.13], [8.22, 53.15], [8.2, 53.13]]] },
    status: "persists", frequency: "many", fictional: true,
  },
  {
    id: 5, title: "Beispiel: getrennte Grünflächen", category: "accessibility",
    scope_kind: "area", location_label: "Zwei fiktive Teilgebiete",
    latitude: null, longitude: null,
    geometry: { type: "MultiPolygon", coordinates: [[[[8.18, 53.13], [8.185, 53.13], [8.185, 53.135], [8.18, 53.13]]]] },
    status: "verified", frequency: "many", fictional: true,
  },
  {
    id: 6, title: "Beispiel: stadtweites Thema", category: "childcare",
    scope_kind: "citywide", location_label: "Gesamtes Stadtgebiet (Beispiel)",
    latitude: null, longitude: null, geometry: null,
    status: "multiple_reports", frequency: "very_many", fictional: true,
  },
  {
    id: 7, title: "Beispiel: kaputte Altgeometrie", category: "mobility",
    scope_kind: "route", location_label: "Fiktiver Altbestand",
    latitude: null, longitude: null,
    geometry: { type: "LineString", coordinates: [[8.2, 53.14]] },
    status: "apparently_resolved", frequency: "several", fictional: true,
  },
];

test.describe("Öffentliche Problemübersicht", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ problems, total: problems.length }),
    }));
  });

  test("zeigt die ehrliche Karte und das vollständige Status-Board ohne Anmeldung", async ({ page }) => {
    await page.goto("/probleme");

    await expect(page.getByRole("heading", { name: "Probleme in Oldenburg" })).toBeVisible();
    await expect(page.getByText("Feature-Vorschau · frei erfundene Beispiele")).toBeVisible();
    await expect(page.getByText("Unabhängig · kein Angebot der Stadt Oldenburg · keine amtlichen Status.")).toBeVisible();
    await expect(page.locator(".problem-map-point")).toHaveCount(1);
    await expect(page.locator(".problem-map-facility")).toHaveCount(1);
    await expect(page.locator(".problem-map-route")).toHaveCount(1);
    await expect(page.locator(".problem-map-area")).toHaveCount(2);
    await expect(page.getByRole("button", { name: /stadtweites Thema/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /kaputte Altgeometrie/i })).toHaveCount(0);
    await expect(page.getByText(/unabhängige Meldung/)).toHaveCount(0);

    await page.locator(".problem-map-route-control").press("Enter");
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Radroute" })).toBeVisible();

    await page.getByRole("button", { name: "Mobilität & Verkehr" }).click();
    await expect(page.getByRole("button", { name: "Mobilität & Verkehr" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".problem-map-facility")).toHaveCount(1);
    await expect(page.locator(".problem-map-route")).toHaveCount(1);
    await expect(page.locator(".problem-map-point")).toHaveCount(0);

    await page.getByRole("button", { name: "Status", exact: true }).click();
    await expect(page).toHaveURL(/view=status/);
    await expect(page.getByRole("button", { name: /stadtweites Thema/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /kaputte Altgeometrie/i })).toBeVisible();
    await expect(page.getByLabel("Kartenthemen")).toHaveCount(0);
  });

  test("legt Beispiel-, Farb- und Statushinweise per Tastatur offen", async ({ page }) => {
    await page.goto("/probleme");

    const exampleInfo = page.getByRole("button", { name: "Mehr zu den fiktiven Beispielen" });
    await expect(page.getByText("Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden.")).toHaveCount(0);
    await expect(page.getByText("Farben zeigen die Zahl unabhängiger Meldungen, nicht die Dringlichkeit.")).toHaveCount(0);
    await expect(page.getByText("Status sind Einordnungen von Ratslotse, keine amtlichen Bearbeitungsstände.")).toHaveCount(0);
    await expect(exampleInfo).toHaveAttribute("aria-expanded", "false");
    await exampleInfo.focus();
    await exampleInfo.press("Enter");
    await expect(exampleInfo).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("dialog", { name: "Fiktive Beispiele" })).toBeVisible();
    await expect(page.getByText("Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(exampleInfo).toHaveAttribute("aria-expanded", "false");
    await expect(exampleInfo).toBeFocused();

    const contextInfo = page.getByRole("button", { name: "Farben und Status erklären" });
    await contextInfo.focus();
    await contextInfo.press("Enter");
    await expect(contextInfo).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("dialog", { name: "Farben und Status" })).toBeVisible();
    await expect(page.getByText("Farben zeigen die Zahl unabhängiger Meldungen, nicht die Dringlichkeit.")).toBeVisible();
    await expect(page.getByText("Status sind Einordnungen von Ratslotse, keine amtlichen Bearbeitungsstände.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(contextInfo).toBeFocused();
  });

  test("meldet ausgefallene Kartenkacheln und lädt sie erneut", async ({ page }) => {
    let tileRequests = 0;
    await page.route("**.basemaps.cartocdn.com/**", (route) => {
      tileRequests += 1;
      return route.abort("failed");
    });
    await page.goto("/probleme");

    await expect(page.getByRole("alert").filter({ hasText: "Karte konnte nicht geladen werden" })).toBeVisible();
    const beforeRetry = tileRequests;
    await page.getByRole("button", { name: "Nochmal versuchen" }).click();
    await expect.poll(() => tileRequests).toBeGreaterThan(beforeRetry);
  });

  test("bietet bei einem Ladefehler einen erneuten Versuch", async ({ page }) => {
    let attempts = 0;
    await page.unroute("**/api/probleme");
    await page.route("**/api/probleme", (route) => {
      attempts += 1;
      return route.fulfill(attempts <= 2 ? {
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Nicht erreichbar" }),
      } : {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ problems: [], total: 0 }),
      });
    });
    await page.goto("/probleme");

    await expect(page.getByRole("alert").filter({ hasText: "Problemkarte konnte nicht geladen werden" })).toBeVisible();
    await page.getByRole("button", { name: "Nochmal versuchen" }).click();
    await expect(page.getByText("Noch keine veröffentlichten Probleme")).toBeVisible();
    expect(attempts).toBe(3);
  });
});

test.describe("Öffentliche Problemübersicht auf schmalem Touch-Gerät", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    colorScheme: "dark",
  });

  test("bleibt im Dark Mode ohne seitliches Seiten-Überlaufen bedienbar", async ({ page }, testInfo) => {
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ problems, total: problems.length }),
    }));
    await page.goto("/probleme");

    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(page.getByLabel("Problemkarte von Oldenburg")).toBeVisible();
    await page.getByRole("button", { name: "Farben und Status erklären" }).tap();
    const explanation = page.getByText("Farben zeigen die Zahl unabhängiger Meldungen, nicht die Dringlichkeit.");
    await expect(explanation).toBeVisible();
    const explanationBox = await explanation.boundingBox();
    expect(explanationBox).not.toBeNull();
    expect(explanationBox!.x).toBeGreaterThanOrEqual(0);
    expect(explanationBox!.x + explanationBox!.width).toBeLessThanOrEqual(390);
    await page.screenshot({ path: testInfo.outputPath("dark-disclosure.png"), fullPage: true });
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Status", exact: true }).tap();
    await expect(page.getByRole("button", { name: /stadtweites Thema/i })).toBeVisible();
    const sizes = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(sizes.page).toBeLessThanOrEqual(sizes.viewport);
  });
});
