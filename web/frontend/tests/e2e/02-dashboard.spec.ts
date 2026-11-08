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

  test("die Tour zeigt das eigene Viertel und die eigenen Themen", async ({ page }) => {
    // Tims Wunsch 08.11.2026: Wer im Assistenten ein Viertel und Themen gewählt
    // hat, sieht sie in der Tour wieder — die Karte fliegt ins Viertel, und die
    // Themen-Station öffnet „Meine Themen" und nennt sie beim Namen. Viertel
    // und Themen kommen gestellt: In der CI ist die Rats-Datenbank leer.
    // Fünf Seiten nacheinander, `/karte` mit Leaflet: `next dev` übersetzt
    // jede beim ersten Aufruf, und die Adresse wechselt erst danach.
    test.slow();
    const themen = [
      { id: 9001, name: "Donnerschwee", description: "Neue Beschlüsse mit Bezug zu Donnerschwee.",
        created_at: "2026-11-08T08:00:00", decision_count: 3, decision_count_capped: false, matched: true },
      { id: 9002, name: "Radverkehr", description: "Radwege und Fahrradstraßen in Oldenburg.",
        created_at: "2026-11-08T08:00:01", decision_count: 10, decision_count_capped: false, matched: true },
    ];
    await page.route((u) => u.pathname === "/api/topics", (route) =>
      route.request().method() === "GET" ? route.fulfill({ json: themen }) : route.continue());
    await page.route((u) => u.pathname === "/api/council/districts", (route) =>
      route.fulfill({ json: { districts: [{ place_id: "donnerschwee", name: "Donnerschwee", kind: "local_area" }] } }));
    await page.route("**/api/app-config", async (route) => {
      const echt = await (await route.fetch()).json();
      await route.fulfill({ json: { ...echt, features: [...new Set([...(echt.features ?? []), "mein-viertel"])] } });
    });
    // Die Tour hakt „Erste Schritte" ab — am GETEILTEN Testkonto. Ohne das
    // stünde die Leiste für die Tests danach auf „Geschafft".
    await page.route((u) => u.pathname === "/api/onboarding", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      await route.fulfill({ json: await (await route.fetch({ method: "GET" })).json() });
    });
    await page.goto("/dashboard");
    await page.evaluate(() => window.dispatchEvent(new Event("ratslotse:start-tour")));
    const tour = page.getByRole("dialog", { name: /^Tour:/ });
    await expect(tour).toBeVisible();
    // Willkommen → Fragen → Beispiel → Suche → Analyse → Karte, jede Station
    // erst, wenn die vorige steht — so klickt auch ein Mensch.
    for (const titel of ["Frag den Rat", "So sieht eine Antwort aus", "Beschlüsse durchsuchen",
      "Zahlen zum Rat", "Dein Viertel"]) {
      await tour.getByRole("button", { name: "Weiter" }).click();
      await expect(tour).toContainText(titel);
    }
    await expect(tour).toContainText("Dein Viertel: Donnerschwee");
    await expect(tour).toContainText("Das ist gerade in Donnerschwee los");
    // Erst die Stadt, dann der Flug ins Viertel.
    await expect(page).toHaveURL(/\/karte\?ort=donnerschwee/, { timeout: 45_000 });
    await page.waitForTimeout(1500); // der Flug dauert 0,7 s
    await page.screenshot({ path: "test-results/screenshots/02-tour-viertel.png" });

    await tour.getByRole("button", { name: "Weiter" }).click();
    await expect(page).toHaveURL(/\/topics/, { timeout: 45_000 });
    await expect(tour).toContainText("die du eben eingerichtet hast: Radverkehr — dazu dein Viertel Donnerschwee.");
    await expect(page.locator("main").getByText("Radverkehr").first()).toBeVisible({ timeout: 45_000 });
    await page.screenshot({ path: "test-results/screenshots/02-tour-themen.png" });
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
