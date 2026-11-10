/**
 * Reiter „Argumente“ und „Fraktionen“ der Punkt-Seite (Schalter
 * `punkt-argumente`, Plan `docs/plan-punkt-argumente.md`).
 *
 * Gestubbt mit einer echten Antwort samt `arguments`
 * (`fixtures/punkt-4702-8-1.json`, VBN-Tarifanpassung 2027 im Rat am
 * 31.08.2026) — läuft so auch gegen die leere Ratsdatenbank.
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PUNKT = JSON.parse(readFileSync(join(__dirname, "fixtures", "punkt-4702-8-1.json"), "utf-8"));
const URL = "/council/punkt?ksinr=4702&top=%C3%96%208.1";

async function stubs(page: Page, features = ["punkt-seite", "punkt-argumente"]) {
  await page.route("**/api/app-config", (route) => route.fulfill({ json: { min_build: 0, features } }));
  await page.route("**/api/council/session/4702/item**", (route) => route.fulfill({ json: PUNKT }));
}

test.describe("Punkt-Seite: Argumente und Fraktionen", () => {
  test("Argumente zuerst, je Aussage Urheber und Fundstelle", async ({ page }) => {
    await stubs(page);
    await page.goto(URL);
    await expect(page.getByRole("tab", { name: /^Argumente/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Worüber gestritten wird" })).toBeVisible();
    await expect(page.getByText(/9 dafür · 7 dagegen oder mit Bedenken/i).first()).toBeVisible();
    const erster = page.locator("article").filter({ hasText: "Streitpunkt 1 von 2" });
    await expect(erster.getByText("Dafür", { exact: true })).toBeVisible();
    await expect(erster.getByText("Dagegen", { exact: true })).toBeVisible();
    await expect(erster.getByRole("link", { name: /Protokoll, S\. \d+/ }).first()).toHaveAttribute("target", "_blank");
  });

  test("„Dazu fragen“ nimmt Punkt und Streitpunkt mit", async ({ page }) => {
    await stubs(page);
    await page.goto(URL);
    const link = page.locator("article").filter({ hasText: "Streitpunkt 1 von 2" }).getByRole("link", { name: "Dazu fragen" });
    const href = await link.getAttribute("href");
    const u = new globalThis.URL(href!, "https://x.test");
    expect(u.pathname).toBe("/fragen");
    expect(u.searchParams.get("ksinr")).toBe("4702");
    expect(u.searchParams.get("top")).toBe("Ö 8.1");
    expect(u.searchParams.get("streit")).toBe(PUNKT.arguments.issues[0].question);
  });

  test("Fraktionen: je Fraktion die ersten drei, der Rest auf Wunsch", async ({ page }) => {
    await stubs(page);
    await page.goto(URL);
    await page.getByRole("tab", { name: /^Fraktionen/ }).click();
    const gruene = page.locator("article").filter({ hasText: "Grüne" }).first();
    await expect(gruene.getByText("7 Wortmeldungen")).toBeVisible();
    await expect(gruene.locator("li")).toHaveCount(3);
    await gruene.getByRole("button", { name: "4 weitere Wortmeldungen" }).click();
    await expect(gruene.locator("li")).toHaveCount(7);
  });

  test("ohne Schalter keine neuen Reiter", async ({ page }) => {
    await stubs(page, ["punkt-seite"]);
    await page.goto(URL);
    await expect(page.getByRole("tab", { name: /^Vorgeschichte/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tab", { name: /^Argumente/ })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: /^Fraktionen/ })).toHaveCount(0);
  });

  for (const breite of [320, 390]) {
    test(`kein seitliches Scrollen bei ${breite} px`, async ({ page }) => {
      await stubs(page);
      await page.setViewportSize({ width: breite, height: 844 });
      await page.goto(URL);
      await expect(page.getByRole("heading", { name: "Worüber gestritten wird" })).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
        .toBeLessThanOrEqual(0);
    });
  }
});
