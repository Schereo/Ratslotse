/**
 * Das Dashboard („Heute"): Begrüßung, Signal-Handlung, Erste Schritte,
 * die beiden kurzen Karten.
 *
 * ÜBERARBEITET am 03.09.2026. Die Datei prüfte bis dahin eine Oberfläche, die
 * es nicht mehr gibt: eine Kachel „Ratsinformationssystem", eine Kachel
 * „Meine Themen", die E-Mail-Adresse im Seiteninhalt und einen Fortschritt
 * „n/6". Die Kacheln sind seit Design 14 durch „Die Woche im Rat" und zwei
 * kurze Karten ersetzt, die Adresse steht nur noch im Konto-Menü, und die
 * Ersten Schritte haben vier Stationen statt sechs — und listen sie nicht
 * mehr einzeln auf, sondern starten eine geführte Tour.
 */
import { test, expect } from "@playwright/test";
import { zustandsDatei } from "./konten";

test.describe("Dashboard", () => {
  // Angemeldet aus der abgelegten Sitzung statt über das Formular — s.
  // `konten.ts`.
  test.use({ storageState: zustandsDatei("admin") });

  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("begrüßt und zeigt die Signal-Handlung", async ({ page }) => {
    // Mit Anzeigenamen „Moin, X!", ohne bloß „Moin!" — beides fängt gleich an.
    await expect(page.getByRole("heading", { name: /^Moin/ })).toBeVisible();
    // DIE eine Handlung des Screens steht als Signal-Knopf daneben.
    await expect(page.locator("main").getByRole("link", { name: "Frag den Rat" })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-dashboard.png", fullPage: true });
  });

  test("Erste Schritte zeigen Fortschritt und führen zur ersten Station", async ({ page }) => {
    // Der Hinweis-Platz zeigt EINEN Hinweis, nach Priorität: Live > Neu bei
    // Ratslotse > Pause > Erste Schritte. Was gerade gewinnt, hängt am Datenstand —
    // in der CI ist die Rats-Datenbank leer, und dann meldet der Server eine
    // Sitzungspause, hinter der die Leiste unter „Mehr" verschwindet. Der Test
    // hat lokal bestanden und in der CI nicht.
    //
    // Deshalb werden die beiden höher stehenden Hinweise hier stillgelegt: Der
    // Test soll die Erste-Schritte-Leiste prüfen, nicht die Tagesform der
    // Sitzungsdaten.
    await page.route("**/api/council/session-break", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ state: "none", label: null, until: null }) }));
    await page.route("**/api/council/heute", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ state: "pause" }) }));
    // Die Release-Karte steht ebenfalls davor. Ein Konto aus der CI ist meist
    // jünger als die Ausgabe und sieht sie nicht — am Release-Tag selbst aber
    // schon.
    await page.route("**/api/news", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ releases: [], older_count: 0, seen_version: null }) }));
    await page.reload();

    const leiste = page.locator("[data-tour='erste-schritte']");
    await expect(leiste).toBeVisible();
    await expect(leiste).toContainText("Erste Schritte mit Lotti");
    // Der Zähler steht neben dem Balken. Die ZAHL der Stationen ist bewusst
    // offen — sie hat sich schon einmal geändert (sechs → vier), und daran
    // soll dieser Test nicht scheitern.
    await expect(leiste.getByText(/^\d\/\d$/)).toBeVisible();
    // Die Leiste listet die Stationen nicht mehr einzeln auf — sie bietet
    // EINEN Knopf, der die geführte Tour startet. Zwei Knöpfe führten früher
    // an verschiedene Orte, und der auffälligere sprang stumm weiter.
    await expect(leiste.getByRole("button", { name: /Tour starten|Weitermachen/ })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-onboarding.png", fullPage: true });
  });

  test("die beiden kurzen Karten stehen da", async ({ page }) => {
    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: /Dein erster Rückblick|Seit deinem letzten Besuch/ })).toBeVisible();
    await expect(main.getByRole("heading", { name: "Zahl der Woche" })).toBeVisible();
  });

  test("die Hauptnavigation führt in den Rat", async ({ page }) => {
    // Seit Design 14 gibt es keine Kachel mehr — der Weg führt über die
    // Navigation. Auf dem Schreibtisch ist das die Seitenleiste.
    await page.getByRole("link", { name: "Suche", exact: true }).first().click();
    await page.waitForURL(/\/council/);
    await page.screenshot({ path: "test-results/screenshots/02-tile-navigation.png", fullPage: true });
  });

  test("auf dem Telefon steht die Leiste unten", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard");
    await expect(page.locator("nav[aria-label='Hauptnavigation']")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-mobile-nav.png", fullPage: true });
  });
});

/** Was „Heute" beim Laden abfragt, und dass Angemeldete gar nicht erst die
 *  Landing laden (Leistungsrunde 11/2026). */
test.describe("Heute ohne Umwege", () => {
  test.use({ storageState: zustandsDatei("admin") });

  test("ein Aufruf für Besuch und Rückblick, eine Sitzungsliste für beide Karten", async ({ page }) => {
    const aufrufe: string[] = [];
    page.on("request", (r) => {
      const u = new URL(r.url());
      if (u.pathname.startsWith("/api/today/") || u.pathname === "/api/council/sessions") {
        aufrufe.push(`${r.method()} ${u.pathname}${u.search}`);
      }
    });
    await page.goto("/dashboard");
    await expect(page.locator("main").getByRole("heading", { name: /Dein erster Rückblick|Seit deinem letzten Besuch/ })).toBeVisible();
    // Ein doppelter POST käme direkt nach dem Einhängen — eine Sekunde reicht.
    await page.waitForTimeout(1000);
    expect(aufrufe.filter((a) => a.startsWith("POST "))).toEqual(["POST /api/today/visit/updates"]);
    expect(aufrufe.filter((a) => a.startsWith("GET /api/today/"))).toEqual([]);
    expect(aufrufe.filter((a) => a.includes("/council/sessions"))).toEqual(["GET /api/council/sessions?scope=upcoming&limit=12"]);
  });

  test("„/“ leitet schon der Server aufs Dashboard, ohne die Landing zu laden", async ({ page }) => {
    const landing: string[] = [];
    page.on("request", (r) => { if (/\/api\/council\/(heute|public-stats)/.test(r.url())) landing.push(r.url()); });
    const antwort = await page.goto("/");
    expect(antwort!.url()).toMatch(/\/dashboard$/);
    // Die Umleitung kam vom Server: Der Seitenaufruf selbst wurde umgelenkt,
    // nicht erst die geladene Landing per Skript ersetzt.
    expect(antwort!.request().redirectedFrom()?.url()).toMatch(/\/$/);
    await expect(page.getByRole("heading", { name: /^Moin/ })).toBeVisible();
    expect(landing).toEqual([]);
  });

  test("die Fluchttür ?start=1 hält die Landing, auch beim nächsten Aufruf", async ({ page }) => {
    await page.goto("/?start=1");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Was beschließt");
    const antwort = await page.goto("/");
    expect(antwort!.request().redirectedFrom()).toBeNull();
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Was beschließt");
  });
});

test("ein ungültiges Sitzungs-Cookie sperrt niemanden von der Startseite aus", async ({ browser, baseURL }) => {
  // Widerrufen (Passwort anderswo geändert) oder mit altem Geheimnis signiert:
  // Das Cookie liegt noch da, die Sitzung gilt nicht mehr. Dann muss die
  // Landing stehen — kein Umweg über /dashboard auf /login.
  const ctx = await browser.newContext({ baseURL });
  await ctx.addCookies([{ name: "access_token", value: "eyJhbGciOiJIUzI1NiJ9.e30.ungueltig", url: baseURL! }]);
  const page = await ctx.newPage();
  const antwort = await page.goto("/");
  expect(antwort!.request().redirectedFrom()).toBeNull();
  await page.waitForTimeout(1500);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Was beschließt");
  await ctx.close();
});
