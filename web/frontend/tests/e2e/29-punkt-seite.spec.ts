/**
 * Die Seite eines Tagesordnungspunkts (Schalter `punkt-seite`, Plan
 * `docs/plan-sitzungsseite-kurs.md`, Schritt 4).
 *
 * Gestubbt mit einer echten Antwort von `/council/session/{ksinr}/item`
 * (`fixtures/punkt-4654-11-1.json`, Weißenmoorstraße im Verkehrsausschuss
 * am 21.09.2026) — der Test läuft so auch gegen die leere Ratsdatenbank.
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));
const SITZUNG = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4654.json"), "utf-8"));

async function stubs(page: Page, features = ["sitzung-kurs", "punkt-seite"]) {
  await page.route("**/api/app-config", (route) => route.fulfill({ json: { min_build: 0, features } }));
  await page.route("**/api/council/session/4654/item**", (route) => route.fulfill({ json: PUNKT }));
  await page.route("**/api/council/session/4654", (route) => route.fulfill({ json: SITZUNG }));
}

test.describe("Punkt-Seite", () => {
  test("zeigt Kurzfassung, Vorgeschichte und Unterlagen ohne Konto", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect(page.getByText("Das Wichtigste in Kürze")).toBeVisible();
    await expect(page.getByRole("tab", { name: /Vorgeschichte/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(/Verkehrsausschuss · diese Sitzung/)).toBeVisible();
    await page.getByRole("tab", { name: /Unterlagen/ }).click();
    await expect(page.getByRole("link", { name: /VCD-Antrag/ })).toHaveAttribute("target", "_blank");
    await expect(page.locator("#password")).toHaveCount(0);
  });

  test("Zurück und Weiter führen durch die Sitzung", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("link", { name: /Weiter Ö 11\.2/ }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2011.2");
    await expect(page.getByRole("link", { name: /Zurück Ö 10/ }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2010");
  });

  test("„Frag den Rat“ reicht den Punkt als Bezug weiter", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    const vorschlag = page.getByRole("link", { name: /Was wurde dazu früher beschlossen\?/ });
    await expect(vorschlag).toHaveAttribute("href", /\/fragen\?q=.*&ksinr=4654&top=%C3%96%2011\.1/);
  });

  test("die Karten der Sitzung führen auf die Seite des Punkts", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/sitzung?ksinr=4654");
    await expect(page.getByRole("link", { name: "Weißenmoorstraße", exact: true }))
      .toHaveAttribute("href", "/council/punkt?ksinr=4654&top=%C3%96%2011.1");
  });

  test("ohne Schalter führt die Seite zur Sitzung", async ({ page }) => {
    await stubs(page, ["sitzung-kurs"]);
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("link", { name: "Zur Sitzung" })).toBeVisible();
  });

  test("kein seitliches Scrollen bei 320 px", async ({ page }) => {
    await stubs(page);
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto("/council/punkt?ksinr=4654&top=%C3%96%2011.1");
    await expect(page.getByRole("heading", { name: "Weißenmoorstraße", level: 1 })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
      .toBeLessThanOrEqual(0);
  });
});
