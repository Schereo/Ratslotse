/**
 * Die neue Sitzungsseite mit dem „Kurs der Sitzung" (Schalter `sitzung-kurs`,
 * Plan `docs/plan-sitzungsseite-kurs.md`, Schritt 3).
 *
 * Die Sitzungen sind gestubbt — echte Antworten von `/council/session`
 * (Verkehrsausschuss 21.09.2026 ohne Protokoll, 24.08.2026 mit;
 * `fixtures/sitzung-kurs-*.json`, `tests/test_browsertest_fixtures.py` hält
 * ihre Felder gleich). So läuft der Test auch gegen die leere Ratsdatenbank
 * der CI. Geprüft wird, was die Seite zusagt: Sie lädt ohne Konto in beiden
 * Zuständen, eine Boje führt zur Karte, der geteilte Punkt ist markiert,
 * und bei 320 px scrollt nichts seitwärts.
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const VORHER = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4654.json"), "utf-8"));
const NACHHER = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4653.json"), "utf-8"));

async function stubs(page: Page, detail: unknown, ksinr: number, features = ["sitzung-kurs"]) {
  await page.route("**/api/app-config", (route) => route.fulfill({ json: { min_build: 0, features } }));
  await page.route(`**/api/council/session/${ksinr}`, (route) => route.fulfill({ json: detail }));
}

test.describe("Sitzungsseite mit Kurs", () => {
  test("vor dem Protokoll: Tafel, Kurs, Wichtiges, Etappen", async ({ page }) => {
    await stubs(page, VORHER, 4654);
    await page.goto("/council/sitzung?ksinr=4654");
    const tafel = page.locator('header[aria-labelledby="sitzung-titel"]');
    await expect(tafel.getByRole("heading", { name: "Verkehr", exact: true })).toBeVisible();
    await expect(tafel.getByText(VORHER.course.summary)).toBeVisible();
    await expect(tafel.getByRole("group", { name: /^Kurs der Sitzung, 17 öffentliche Punkte in 5 Etappen$/ })).toBeVisible();
    await expect(tafel.getByText("Wichtig in dieser Sitzung")).toBeVisible();
    // Etappen wie im Entwurf.
    for (const name of ["Zum Start", "Beschlüsse und Berichte", "Anträge", "Zum Schluss", "Nichtöffentlicher Teil"]) {
      await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Drei Widmungen" })).toBeVisible();
    await expect(page.getByText("Das Ratsinfo sperrt hier auch die Überschriften.", { exact: false })).toBeVisible();
    // Der Weg ins Konto steht weiter am Fuß, nicht davor.
    await expect(page.locator("#password")).toHaveCount(0);
  });

  test("eine Boje führt zur Karte ihres Punktes", async ({ page }) => {
    await stubs(page, VORHER, 4654);
    await page.goto("/council/sitzung?ksinr=4654");
    const boje = page.getByRole("link", { name: /^Ö 9 · Soziales D-Ticket in Oldenburg/ });
    await expect(boje).toBeVisible();
    await boje.click();
    await expect(page).toHaveURL(/#top-4654-/);
    await expect(page.getByRole("heading", { name: "Soziales D-Ticket in Oldenburg", level: 4 })).toBeInViewport();
  });

  test("nach dem Protokoll: Ergebnisse, Zählung, Weg der Vorlage, wie es weitergeht", async ({ page }) => {
    await stubs(page, NACHHER, 4653);
    await page.goto("/council/sitzung?ksinr=4653");
    const tafel = page.locator('header[aria-labelledby="sitzung-titel"]');
    await expect(tafel.getByText(/von 30 öffentlichen Punkten hatten eines/)).toBeVisible();
    await expect(tafel.getByRole("link", { name: "Protokoll" })).toHaveAttribute("target", "_blank");
    await expect(page.getByText("Wie es weitergeht").first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Zur Sitzung am 21\.09\.2026/ }).first()).toBeVisible();
  });

  test("hebt den geteilten Tagesordnungspunkt hervor", async ({ page }) => {
    await stubs(page, VORHER, 4654);
    await page.goto("/council/sitzung?ksinr=4654&top=%C3%96%2010");
    const karte = page.locator("article", { hasText: "Geschwindigkeitsmessung" }).first();
    await expect(karte).toHaveClass(/ring-primary/, { timeout: 10_000 });
  });

  test("schaltet ohne Schalter auf die bisherige Seite zurück", async ({ page }) => {
    await stubs(page, VORHER, 4654, []);
    await page.goto("/council/sitzung?ksinr=4654");
    await expect(page.getByText("Tagesordnungspunkte", { exact: false }).first()).toBeVisible();
    await expect(page.getByRole("group", { name: /^Kurs der Sitzung/ })).toHaveCount(0);
  });

  for (const breite of [320, 390]) {
    test(`kein seitliches Scrollen bei ${breite} px`, async ({ page }) => {
      await stubs(page, NACHHER, 4653);
      await page.setViewportSize({ width: breite, height: 844 });
      await page.goto("/council/sitzung?ksinr=4653");
      await expect(page.getByRole("group", { name: /^Kurs der Sitzung/ })).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
        .toBeLessThanOrEqual(0);
    });
  }
});
