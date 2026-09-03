import { expect, test } from "@playwright/test";
import type { ProblemList } from "@/lib/probleme";

const problems = [
  {
    id: 1, title: "Beispiel: dunkler Fußweg", category: "public_space",
    summary: "Fiktive Zusammenfassung einer fehlenden Beleuchtung.", independent_reports: 3,
    scope_kind: "point", location_label: "Fiktiver Beispielort",
    latitude: 53.14, longitude: 8.21, geometry: null,
    status: "multiple_reports", frequency: "several", fictional: true,
  },
  {
    id: 2, title: "Beispiel: Musterhalle", category: "mobility",
    summary: "Fiktive Zusammenfassung zu einer erfundenen Einrichtung.", independent_reports: 11,
    scope_kind: "facility", location_label: "Fiktive Musterhalle",
    latitude: 53.145, longitude: 8.22, geometry: null,
    status: "verified", frequency: "very_many", fictional: true,
  },
  {
    id: 3, title: "Beispiel: Radroute", category: "mobility",
    summary: "Fiktiver Streckenabschnitt für die Routendarstellung.", independent_reports: 1,
    scope_kind: "route", location_label: "Fiktive Beispielroute",
    latitude: null, longitude: null,
    geometry: { type: "LineString", coordinates: [[8.19, 53.14], [8.22, 53.15]] },
    status: "new", frequency: "once", fictional: true,
  },
  {
    id: 4, title: "Beispiel: Musterquartier", category: "environment",
    summary: "Fiktive Fläche für die Polygondarstellung.", independent_reports: 7,
    scope_kind: "area", location_label: "Fiktives Musterquartier",
    latitude: null, longitude: null,
    geometry: { type: "Polygon", coordinates: [[[8.2, 53.13], [8.22, 53.13], [8.22, 53.15], [8.2, 53.13]]] },
    status: "persists", frequency: "many", fictional: true,
  },
  {
    id: 5, title: "Beispiel: getrennte Grünflächen", category: "accessibility",
    summary: "Fiktive getrennte Flächen für die MultiPolygon-Darstellung.", independent_reports: 7,
    scope_kind: "area", location_label: "Zwei fiktive Teilgebiete",
    latitude: null, longitude: null,
    geometry: { type: "MultiPolygon", coordinates: [[[[8.18, 53.13], [8.185, 53.13], [8.185, 53.135], [8.18, 53.13]]]] },
    status: "verified", frequency: "many", fictional: true,
  },
  {
    id: 6, title: "Beispiel: stadtweites Thema", category: "childcare",
    summary: "Fiktives stadtweites Problem ohne erfundenen Kartenpunkt.", independent_reports: 18,
    scope_kind: "citywide", location_label: "Gesamtes Stadtgebiet (Beispiel)",
    latitude: null, longitude: null, geometry: null,
    status: "multiple_reports", frequency: "very_many", fictional: true,
  },
  {
    id: 7, title: "Beispiel: kaputte Altgeometrie", category: "mobility",
    summary: "Fiktiver Altbestand mit unbrauchbarer Geometrie.", independent_reports: 2,
    scope_kind: "route", location_label: "Fiktiver Altbestand",
    latitude: null, longitude: null,
    geometry: { type: "LineString", coordinates: [[8.2, 53.14]] },
    status: "new", frequency: "several", fictional: true,
  },
] satisfies ProblemList["problems"];

const rankedProblems = [...problems].sort((a, b) => (
  b.independent_reports - a.independent_reports
  || a.title.localeCompare(b.title, "de")
  || a.id - b.id
));
const problemResponse = {
  problems: rankedProblems,
  total: rankedProblems.length,
} satisfies ProblemList;

test.describe("Öffentliche Problemübersicht", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(problemResponse),
    }));
  });

  test("zeigt Karte und Meistgemeldet-Rangliste ohne Anmeldung", async ({ page }, testInfo) => {
    const runtimeErrors: string[] = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.stack ?? error.message));
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

    await page.locator(".problem-map-route-control").press("Enter");
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Radroute" })).toBeVisible();
    await expect(page.getByText("1 unabhängige Meldung", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Mobilität & Verkehr" }).click();
    await expect(page.getByRole("button", { name: "Mobilität & Verkehr" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".problem-map-facility")).toHaveCount(1);
    await expect(page.locator(".problem-map-route")).toHaveCount(1);
    await expect(page.locator(".problem-map-point")).toHaveCount(0);

    await page.getByRole("button", { name: "Meistgemeldet", exact: true }).click();
    await expect(page).toHaveURL(/view=meistgemeldet/);
    await expect(page.getByRole("heading", { name: "Meistgemeldet" })).toBeVisible();
    await expect(page.getByText(/gemeinschaftliche Aufmerksamkeit.*keine Aussage über Wahrheit, Dringlichkeit/i)).toBeVisible();
    await expect(page.getByLabel("Hafenblau-Skala der Meldehäufigkeit")).toBeVisible();
    const entries = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" }).getByRole("listitem");
    await expect(entries).toHaveCount(7);
    await expect(entries.nth(0)).toContainText("Beispiel: stadtweites Thema");
    await expect(entries.nth(0)).toContainText("18 unabhängige Meldungen");
    await expect(entries.nth(1)).toContainText("11 unabhängige Meldungen");
    await expect(entries.nth(2)).toContainText("Beispiel: getrennte Grünflächen");
    await expect(entries.nth(3)).toContainText("Beispiel: Musterquartier");
    await expect(page.locator('[data-ranggruppe="top-drei"]')).toHaveCount(3);
    const attribution = page.locator("figcaption").filter({
      hasText: "Quelle der Rangfolge: Freigegebene unabhängige Meldungen im Ratslotse-Meldungsbestand · gesamter Zeitraum",
    });
    await expect(attribution).toBeVisible();
    await expect(page.locator(".problem-rank-bar").first()).toHaveCSS("transition-duration", "0s");
    const rank = entries.nth(0).getByText("01", { exact: true });
    await expect(rank).toHaveCSS("font-family", /Inter/);
    expect(await rank.evaluate((element) => getComputedStyle(element).fontFamily)).not.toMatch(/Bricolage/i);
    await expect(page.getByText("Offenbar behoben")).toHaveCount(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath("meistgemeldet-desktop-light.png"), fullPage: true });
    expect(runtimeErrors).toEqual([]);
  });

  test("zeichnet auch bei großer Zahlenspanne mathematisch proportionale Rangbalken", async ({ page }) => {
    const spreadResponse = {
      problems: [
        {
          ...problems[5],
          id: 101,
          title: "Beispiel: sehr häufig bestätigt",
          independent_reports: 10_000,
        },
        {
          ...problems[2],
          id: 102,
          title: "Beispiel: einmal bestätigt",
          independent_reports: 1,
        },
      ],
      total: 2,
    } satisfies ProblemList;
    await page.unroute("**/api/probleme");
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(spreadResponse),
    }));

    await page.goto("/probleme?view=meistgemeldet");

    const entries = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" }).getByRole("listitem");
    await expect(entries.nth(0).locator(".problem-rank-bar")).toHaveAttribute("style", "width: 100%;");
    await expect(entries.nth(1).locator(".problem-rank-bar")).toHaveAttribute("style", "width: 0.01%;");
  });

  test("klappt Vorschauen per Tastatur auf und fokussiert ehrliche Geometrien", async ({ page }) => {
    await page.goto("/probleme?view=meistgemeldet");

    const citywide = page.getByRole("button", { name: /1\. Beispiel: stadtweites Thema.*18 unabhängige Meldungen/i });
    await expect(citywide).toHaveAttribute("aria-expanded", "false");
    await citywide.focus();
    await citywide.press("Enter");
    await expect(citywide).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText("Kein einzelner Kartenort: Dieses Beispiel gilt für das gesamte Stadtgebiet.")).toBeVisible();
    await expect(page.getByRole("button", { name: /stadtweites Thema auf der Karte zeigen/i })).toHaveCount(0);

    const facility = page.getByRole("button", { name: /2\. Beispiel: Musterhalle.*11 unabhängige Meldungen/i });
    await facility.focus();
    await facility.press("Space");
    await expect(facility).toHaveAttribute("aria-expanded", "true");
    await expect(citywide).toHaveAttribute("aria-expanded", "false");
    await page.getByRole("button", { name: "Beispiel: Musterhalle auf der Karte zeigen" }).click();
    await expect(page.getByRole("button", { name: "Karte", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".problem-map-facility.is-selected")).toHaveCount(1);
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Musterhalle" })).toBeVisible();

    await page.getByRole("button", { name: "Meistgemeldet", exact: true }).click();
    await page.getByRole("button", { name: /Beispiel: kaputte Altgeometrie/i }).click();
    await expect(page.getByText("Keine brauchbare Geometrie: Dieses Beispiel kann nicht ehrlich auf der Karte gezeigt werden.")).toBeVisible();

    await page.getByRole("combobox", { name: "Status filtern" }).selectOption("verified");
    const filtered = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" }).getByRole("listitem");
    await expect(filtered).toHaveCount(2);
    await expect(filtered.nth(0)).toContainText("Musterhalle");
    await expect(filtered.nth(1)).toContainText("getrennte Grünflächen");
  });

  test("fokussiert Punkt, Einrichtung, Route und Gebiet aus der Rangliste", async ({ page }) => {
    const cases = [
      { title: "Beispiel: dunkler Fußweg", selected: ".problem-map-point.is-selected" },
      { title: "Beispiel: Musterhalle", selected: ".problem-map-facility.is-selected" },
      { title: "Beispiel: Radroute", selected: '.problem-map-route-control[aria-pressed="true"]' },
      { title: "Beispiel: Musterquartier", selected: '.problem-map-area-control[aria-pressed="true"]' },
    ];

    for (const example of cases) {
      await page.goto("/probleme?view=meistgemeldet");
      await page.getByRole("button", { name: new RegExp(example.title, "i") }).click();
      await page.getByRole("button", { name: `${example.title} auf der Karte zeigen` }).click();
      await expect(page.locator(example.selected)).toHaveCount(1);
      await expect(page.getByRole("heading", { level: 2, name: example.title })).toBeVisible();
    }
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
        body: JSON.stringify({ problems: [], total: 0 } satisfies ProblemList),
      });
    });
    await page.goto("/probleme");

    await expect(page.getByRole("alert").filter({ hasText: "Problemkarte konnte nicht geladen werden" })).toBeVisible();
    await page.getByRole("button", { name: "Nochmal versuchen" }).click();
    await expect(page.getByText("Noch keine veröffentlichten ungelösten Probleme")).toBeVisible();
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
    await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(problemResponse),
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
    await page.getByRole("button", { name: "Meistgemeldet", exact: true }).tap();
    await expect(page.getByRole("button", { name: /stadtweites Thema/i })).toBeVisible();
    await expect(page.locator(".problem-rank-bar").first()).toHaveCSS("transition-duration", "0s");
    const citywideToggle = page.getByRole("button", { name: /1\. Beispiel: stadtweites Thema/i });
    await expect(citywideToggle.locator("svg")).toHaveCSS("transition-duration", "0s");
    await expect(citywideToggle.locator("xpath=..")).toHaveCSS("transition-duration", "0s");
    await citywideToggle.tap();
    await expect(page.getByText("Kein einzelner Kartenort: Dieses Beispiel gilt für das gesamte Stadtgebiet.")).toBeVisible();
    await expect(page.locator(".problem-preview")).toHaveCSS("animation-name", "none");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath("meistgemeldet-mobile-dark.png"), fullPage: true });
    const sizes = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(sizes.page).toBeLessThanOrEqual(sizes.viewport);

    await page.getByRole("button", { name: /2\. Beispiel: Musterhalle/i }).tap();
    await page.getByRole("button", { name: "Beispiel: Musterhalle auf der Karte zeigen" }).tap();
    const selectedFacility = page.locator(".problem-map-facility.is-selected");
    await expect(selectedFacility).toHaveCount(1);
    await expect(selectedFacility).toHaveCSS("transition-duration", "0s");
    await expect(page.locator(".problem-map-route")).toHaveCSS("transition-duration", "0s");
    await expect(page.locator(".problem-map-area").first()).toHaveCSS("transition-duration", "0s");
  });
});
