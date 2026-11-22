/**
 * Mitlesen während der Sitzung (Schalter `mitlesen`, Plan
 * `docs/plan-sitzungsseite-kurs.md`, Schritt 5).
 *
 * Gestubbt mit der echten Sitzung vom 21.09.2026 (Ausschuss, keine
 * Übertragung): Man gibt selbst den Takt vor. Geprüft wird Weiter und
 * Zurück, eine Boje wählen, und dass Neuladen den Punkt behält.
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SITZUNG = JSON.parse(readFileSync(join(__dirname, "fixtures", "sitzung-kurs-4654.json"), "utf-8"));
const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4654-11-1.json"), "utf-8"));

async function stubs(page: Page) {
  await page.route("**/api/app-config", (route) =>
    route.fulfill({ json: { min_build: 0, features: ["sitzung-kurs", "punkt-seite", "mitlesen"] } }));
  await page.route("**/api/council/session/4654/item**", (route) => route.fulfill({ json: PUNKT }));
  await page.route("**/api/council/session/4654", (route) => route.fulfill({ json: SITZUNG }));
}

const jetztDran = (page: Page) => page.locator("article", { hasText: "Jetzt dran" });

test.describe("Mitlesen", () => {
  test("Weiter und Zurück, ohne Übertragung mit dem Satz dazu", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await expect(page.getByText("Ratslotse weiß nicht, wo die Sitzung gerade ist.").first()).toBeVisible();
    await expect(page.locator("#jetzt-titel")).toHaveText("Formalien");
    // Am Anfang gibt es kein Zurück.
    await expect(page.getByRole("button", { name: /^Zurück zu/ })).toHaveCount(0);
    await page.getByRole("button", { name: /^Weiter Ö 4/ }).first().click();
    await expect(page.locator("#jetzt-titel")).toHaveText("Einwohnerfragestunde");
    await expect(page.getByText(/Boje 2 von 13/)).toBeVisible();
    await page.getByRole("button", { name: /^Zurück zu Ö 1–3/ }).first().click();
    await expect(page.locator("#jetzt-titel")).toHaveText("Formalien");
  });

  test("eine Boje wählen und neu laden behält den Punkt", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await page.getByRole("button", { name: /^Ö 9 · Soziales D-Ticket in Oldenburg/ }).click();
    await expect(page.locator("#jetzt-titel")).toHaveText("Soziales D-Ticket in Oldenburg");
    await expect(page.getByRole("button", { name: /^Ö 9 · Soziales D-Ticket/ })).toHaveAttribute("aria-current", "step");
    await page.reload();
    await expect(page.locator("#jetzt-titel")).toHaveText("Soziales D-Ticket in Oldenburg");
  });

  test("am Ende der nichtöffentliche Teil, ohne Weiter", async ({ page }) => {
    await stubs(page);
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await page.getByRole("button", { name: /^Weiter/ }).first().waitFor();
    for (let i = 0; i < 12; i++) await page.getByRole("button", { name: /^Weiter/ }).first().click();
    await expect(page.locator("#jetzt-titel")).toHaveText("Nichtöffentlicher Teil");
    await expect(page.getByRole("button", { name: /^Weiter/ })).toHaveCount(0);
  });

  test("kein seitliches Scrollen bei 320 px", async ({ page }) => {
    await stubs(page);
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto("/council/sitzung/mitlesen?ksinr=4654");
    await expect(jetztDran(page)).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
      .toBeLessThanOrEqual(0);
  });
});
