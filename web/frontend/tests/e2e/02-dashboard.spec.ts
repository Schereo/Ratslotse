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
import { loginAdmin } from "./helpers";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
    await page.goto("/dashboard");
  });

  test("begrüßt und zeigt die Signal-Handlung", async ({ page }) => {
    // Ohne Anzeigenamen bleibt es beim bloßen „Moin!".
    await expect(page.getByRole("heading", { name: /^Moin/ })).toBeVisible();
    // DIE eine Handlung des Screens steht als Signal-Knopf daneben.
    await expect(page.locator("main").getByRole("link", { name: "Frag den Rat" })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-dashboard.png", fullPage: true });
  });

  test("Erste Schritte zeigen Fortschritt und führen zur ersten Station", async ({ page }) => {
    // Der Hinweis-Platz zeigt EINEN Hinweis, nach Priorität: Live > Pause >
    // Erste Schritte > Mitteilungen. Was gerade gewinnt, hängt am Datenstand —
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
    await expect(main.getByRole("heading", { name: "Neu zu deinen Themen" })).toBeVisible();
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
