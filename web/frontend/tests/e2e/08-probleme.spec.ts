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

  test("hält Produkterklärungen hinter der Lotti-Hilfe statt dauerhaft im Weg", async ({ page }) => {
    await page.goto("/probleme?view=meistgemeldet");
    await expect(page.getByRole("heading", { name: "Meistgemeldet" })).toBeVisible();

    // Post-merge feedback from the deployed feature: these five signals were
    // archived together and must remain guarded at the browser seam.
    await expect.soft(page.getByText("Meldehäufigkeit", { exact: true })).toHaveCount(0, { timeout: 500 });
    await expect.soft(page.getByText(/Die lebenszeitliche Zahl unabhängiger freigegebener Meldungen zeigt/)).toHaveCount(0, { timeout: 500 });
    await expect.soft(page.getByLabel("Status filtern")).toHaveCount(0, { timeout: 500 });
    await expect.soft(page.getByText("Mehrfach gemeldet", { exact: true })).toHaveCount(0, { timeout: 500 });
    await expect.soft(page.getByRole("button", { name: /Lotti.*Hilfe/i })).toBeVisible({ timeout: 500 });
  });

  test("zeigt Karte und Meistgemeldet-Rangliste ohne Anmeldung", async ({ page }, testInfo) => {
    const runtimeErrors: string[] = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.stack ?? error.message));
    await page.goto("/probleme");

    await expect(page.getByRole("heading", { name: "Probleme in Oldenburg" })).toBeVisible();
    await expect(page.getByText("Feature-Vorschau · frei erfundene Beispiele")).toBeVisible();
    await expect(page.getByText("Unabhängige Meldungen · privates Bürgerprojekt, kein Angebot der Stadt Oldenburg.")).toBeVisible();
    await expect(page.locator(".problem-map-point")).toHaveCount(1);
    await expect(page.locator(".problem-map-facility")).toHaveCount(1);
    await expect(page.locator(".problem-map-route")).toHaveCount(1);
    await expect(page.locator(".problem-map-area")).toHaveCount(2);
    await expect(page.getByRole("button", { name: /stadtweites Thema/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /kaputte Altgeometrie/i })).toHaveCount(0);

    await page.locator(".problem-map-route-control").press("Enter");
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Radroute" })).toBeVisible();
    await expect(page.getByText("1 unabhängige Meldung", { exact: true })).toBeVisible();
    for (const status of ["Neu", "Mehrfach gemeldet", "Geprüft", "Weiterhin vorhanden"]) {
      await expect(page.getByText(status, { exact: true })).toHaveCount(0);
    }

    await page.getByRole("button", { name: "Mobilität & Verkehr" }).click();
    await expect(page.getByRole("button", { name: "Mobilität & Verkehr" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".problem-map-facility")).toHaveCount(1);
    await expect(page.locator(".problem-map-route")).toHaveCount(1);
    await expect(page.locator(".problem-map-point")).toHaveCount(0);

    await page.getByRole("button", { name: "Meistgemeldet", exact: true }).click();
    await expect(page).toHaveURL(/view=meistgemeldet/);
    await expect(page.getByRole("heading", { name: "Meistgemeldet" })).toBeVisible();
    await expect(page.getByText(/gemeinschaftliche Aufmerksamkeit.*keine Aussage über Wahrheit, Dringlichkeit/i)).toHaveCount(0);
    await expect(page.getByLabel("Hafenblau-Skala der Meldehäufigkeit")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Lotti-Hilfe öffnen: Rangliste erklären/i })).toBeVisible();
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
    const exactCount = entries.nth(0).getByText("18 unabhängige Meldungen", { exact: true });
    await expect(rank).toHaveCSS("font-family", /Inter|IBM Plex Mono/);
    await expect(exactCount).toHaveCSS("font-family", /Inter|IBM Plex Mono/);
    expect(await rank.evaluate((element) => getComputedStyle(element).fontFamily)).not.toMatch(/Bricolage/i);
    expect(await exactCount.evaluate((element) => getComputedStyle(element).fontFamily)).not.toMatch(/Bricolage/i);
    await expect(page.getByText("Offenbar behoben")).toHaveCount(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath("meistgemeldet-desktop-light.png"), fullPage: true });
    expect(runtimeErrors).toEqual([]);
  });

  test("nutzt Desktopbreite für eine klar hierarchische Top drei", async ({ page }) => {
    await page.goto("/probleme?view=meistgemeldet");

    const entries = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" }).getByRole("listitem");
    await expect(entries).toHaveCount(7);
    const [first, second, third, fourth] = await Promise.all([
      entries.nth(0).boundingBox(),
      entries.nth(1).boundingBox(),
      entries.nth(2).boundingBox(),
      entries.nth(3).boundingBox(),
    ]);
    expect(first).not.toBeNull();
    expect(second).not.toBeNull();
    expect(third).not.toBeNull();
    expect(fourth).not.toBeNull();
    expect(Math.abs(first!.y - second!.y)).toBeLessThanOrEqual(4);
    expect(Math.abs(second!.y - third!.y)).toBeLessThanOrEqual(4);
    expect(first!.width).toBeGreaterThan(second!.width * 1.5);
    expect(first!.height).toBeGreaterThan(fourth!.height * 1.25);

    // A wide window can still contain a narrow card area (for example beside
    // navigation). Layout therefore follows the graphic's container, not the viewport.
    const list = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" });
    await list.evaluate((element) => {
      (element.parentElement as HTMLElement).style.width = "760px";
    });
    const [narrowFirst, narrowSecond] = await Promise.all([
      entries.nth(0).boundingBox(),
      entries.nth(1).boundingBox(),
    ]);
    expect(narrowFirst).not.toBeNull();
    expect(narrowSecond).not.toBeNull();
    expect(Math.abs(narrowFirst!.width - narrowSecond!.width)).toBeLessThanOrEqual(2);
    expect(narrowSecond!.y).toBeGreaterThan(narrowFirst!.y + narrowFirst!.height);
  });

  test("bindet Bewegung an Eintritt, Fokus, Auswahl und Lotti-Hilfe", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/probleme?view=meistgemeldet");

    const first = page.locator('[data-ranggruppe="top-drei"]').first();
    const toggle = first.getByRole("button", { name: /1\. Beispiel: stadtweites Thema/i });
    const bar = first.locator(".problem-rank-bar");
    expect(await first.evaluate((element) => getComputedStyle(element).animationName)).not.toBe("none");
    expect(await bar.evaluate((element) => getComputedStyle(element).animationName)).not.toBe("none");
    const durations = await Promise.all([
      first.evaluate((element) => getComputedStyle(element).animationDuration),
      bar.evaluate((element) => getComputedStyle(element).animationDuration),
    ]);
    expect(durations.map((duration) => Number.parseFloat(duration))).toEqual([
      expect.any(Number),
      expect.any(Number),
    ]);
    expect(durations.every((duration) => Number.parseFloat(duration) <= 0.3)).toBe(true);
    await expect(bar).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
    const borderBeforeHover = await first.evaluate((element) => getComputedStyle(element).borderColor);
    await toggle.hover();
    await expect.poll(() => first.evaluate((element) => getComputedStyle(element).transform)).not.toBe("none");
    const hoverStyle = await first.evaluate((element) => ({
      border: getComputedStyle(element).borderColor,
      shadow: getComputedStyle(element).boxShadow,
    }));
    expect(hoverStyle.border).not.toBe(borderBeforeHover);
    expect(hoverStyle.shadow).toContain("1px 2px");
    expect(hoverStyle.shadow).not.toContain("24px");
    await toggle.click();
    expect(await page.locator(".problem-preview").evaluate((element) => getComputedStyle(element).animationName)).not.toBe("none");

    const help = page.getByRole("button", { name: "Lotti-Hilfe öffnen: Rangliste erklären" });
    await expect(help.locator("lotti-figur")).toHaveAttribute("regung", "zeigt-runter");
    await help.click();
    await expect(page.getByRole("button", { name: "Lotti-Hilfe schließen: Rangliste erklären" }).locator("lotti-figur")).toHaveAttribute("regung", "erklaert");
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

  test("Lotti erklärt Karte und Rangliste per Tastatur und gibt den Fokus zurück", async ({ page }) => {
    await page.goto("/probleme");

    await expect(page.getByRole("button", { name: "Mehr zu den fiktiven Beispielen" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Farben und Status erklären" })).toHaveCount(0);
    await expect(page.getByText("Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden.")).toHaveCount(0);
    await expect(page.getByLabel("Hafenblau-Skala der Meldehäufigkeit")).toHaveCount(0);

    const mapHelp = page.getByRole("button", { name: "Lotti-Hilfe öffnen: Karte erklären" });
    await expect(mapHelp).toHaveAttribute("aria-expanded", "false");
    await expect(mapHelp.locator("lotti-figur")).toHaveAttribute("regung", "ruht");
    await mapHelp.focus();
    await mapHelp.press("Enter");

    const dialog = page.getByRole("dialog", { name: "Lotti erklärt die Karte" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toBeFocused();
    await expect(page.getByRole("button", { name: "Lotti-Hilfe schließen: Karte erklären" })).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("button", { name: /Lotti-Hilfe schließen/ }).locator("lotti-figur")).toHaveAttribute("regung", "erklaert");
    await expect(page.getByLabel("Hafenblau-Skala der Meldehäufigkeit")).toBeVisible();
    await expect(page.getByText(/Hafenblau zeigt ausschließlich die Zahl unabhängiger Meldungen/)).toBeVisible();
    await expect(page.getByText("Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden. Sie zeigen nur, wie die Übersicht funktioniert.")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(mapHelp).toHaveAttribute("aria-expanded", "false");
    await expect(mapHelp).toBeFocused();

    await page.getByRole("button", { name: "Meistgemeldet", exact: true }).click();
    const leaderboardHelp = page.getByRole("button", { name: "Lotti-Hilfe öffnen: Rangliste erklären" });
    await expect(leaderboardHelp.locator("lotti-figur")).toHaveAttribute("regung", "zeigt-runter");
    await leaderboardHelp.press("Enter");
    await expect(page.getByRole("dialog", { name: "Lotti erklärt die Rangliste" })).toBeVisible();
    await expect(page.getByText(/Die lebenszeitliche Zahl zählt freigegebene unabhängige Meldungen/)).toBeVisible();
    await page.getByRole("button", { name: "Hilfe schließen", exact: true }).click();
    await expect(leaderboardHelp).toBeFocused();
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
    await page.getByRole("button", { name: "Lotti-Hilfe öffnen: Karte erklären" }).tap();
    const explanation = page.getByText(/Hafenblau zeigt ausschließlich die Zahl unabhängiger Meldungen/);
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
    await expect(page.locator('[data-ranggruppe="top-drei"]').first()).toHaveCSS("animation-name", "none");
    await expect(page.locator(".problem-rank-bar").first()).toHaveCSS("animation-name", "none");
    const lottiHelp = page.getByRole("button", { name: "Lotti-Hilfe öffnen: Rangliste erklären" });
    await expect(lottiHelp).toHaveCSS("transition-duration", "0s");
    await expect(lottiHelp.locator("lotti-figur")).toHaveCSS("transition-duration", "0s");
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

test("bleibt zusätzlich auf Desktop dunkel und Mobile hell stimmig", async ({ browser }, testInfo) => {
  const variants = [
    { name: "desktop-dark", viewport: { width: 1440, height: 900 }, colorScheme: "dark" as const, hasTouch: false },
    { name: "mobile-light", viewport: { width: 390, height: 844 }, colorScheme: "light" as const, hasTouch: true },
  ];

  for (const variant of variants) {
    const context = await browser.newContext({
      viewport: variant.viewport,
      colorScheme: variant.colorScheme,
      hasTouch: variant.hasTouch,
      reducedMotion: "no-preference",
    });
    await context.addInitScript((theme) => localStorage.setItem("theme", theme), variant.colorScheme);
    const page = await context.newPage();
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(problemResponse),
    }));
    await page.goto("/probleme?view=meistgemeldet");

    if (variant.colorScheme === "dark") await expect(page.locator("html")).toHaveClass(/dark/);
    else await expect(page.locator("html")).not.toHaveClass(/dark/);
    await expect(page.getByRole("heading", { name: "Meistgemeldet" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Lotti-Hilfe öffnen: Rangliste erklären" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    const finalEntry = page.getByRole("list", { name: "Meistgemeldete ungelöste Probleme" }).getByRole("listitem").last();
    await expect(finalEntry).toHaveCSS("opacity", "1");
    await expect(finalEntry.locator(".problem-rank-bar")).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
    await page.screenshot({ path: testInfo.outputPath(`${variant.name}.png`), fullPage: true });
    await context.close();
  }
});
