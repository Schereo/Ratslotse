/** Fixture: scripts/stichwahl_potenzial.py --json <fixtures/stichwahl-analyse.json>
 * tests/test_browsertest_fixtures.py hält vollständige Gleichheit. */
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const ANALYSE = JSON.parse(readFileSync(path.join(__dirname, "fixtures", "stichwahl-analyse.json"), "utf8"));
const TOKEN = "probe-token-fuer-die-browsertests";
const URL = `/stichwahl/potenzial?k=${TOKEN}`;

async function analyseMock(page: Page, fehler = false): Promise<string[]> {
  const anfragen: string[] = [];
  await page.route("**/api/wahlabend/stichwahl/potenzial*", (route) => {
    const url = route.request().url();
    anfragen.push(url);
    const status = fehler ? 503 : url.includes(`token=${TOKEN}`) ? 200 : 404;
    return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(status === 200 ? ANALYSE : { detail: "Not Found" }) });
  });
  return anfragen;
}

test.describe("Stichwahlanalyse", () => {
  test("der private Link bleibt geschützt", async ({ page }) => {
    const anfragen = await analyseMock(page);
    await page.goto("/stichwahl/potenzial");
    await expect(page.getByTestId("analyse-fehlt")).toBeVisible();
    expect(anfragen).toHaveLength(0);
    await page.goto("/stichwahl/potenzial?k=falsch-und-lang-genug-1234");
    await expect(page.getByTestId("analyse-fehlt")).toBeVisible();
    await expect.poll(() => anfragen.length).toBeGreaterThan(0);
    await expect(page.getByTestId("analyse-tafel")).toHaveCount(0);
  });

  test("vollständige Ergebnisse, nachvollziehbarer Nennerwechsel und Quellen", async ({ page }) => {
    const anfragen = await analyseMock(page);
    await page.goto(URL);
    await expect(page.getByTestId("analyse-tafel")).toContainText("30.731");
    await expect(page.locator("#wahlbeteiligung")).toContainText("49.522");
    await expect(page.locator("#ratswahl")).toContainText("34.335");
    const ergebnis = page.getByTestId("kandidaten-ergebnis");
    await expect(ergebnis).toContainText("Michael Stille und Yakup Castur");
    await expect(ergebnis).toContainText("1.509");
    const brief = page.getByTestId("wahlart-Briefwahl");
    await expect(brief).toContainText("34,8");
    await expect(brief).toContainText("27.122");
    await page.getByRole("button", { name: "Nur Prange und Rohr", exact: true }).click();
    await expect(brief).toContainText("51,1");
    await expect(brief).toContainText("18.499");
    await expect(brief).toContainText("9.447");
    await expect(page.getByTestId("bezugsbasis")).toContainText("herausgerechnet");
    expect(anfragen).toHaveLength(1);
    const h14 = page.getByTestId("historie-2014");
    await expect(h14).toContainText("86,9");
    await h14.getByText("Stimmenzahlen und Wachstum beider Kandidaten", { exact: true }).click();
    await expect(h14.getByRole("table")).toContainText("6.523");
    await expect(page.getByTestId("historie-2021")).toContainText("6,47");
    await expect(page.getByRole("link", { name: "Quelle: Stichwahl 2021" })).toHaveAttribute("href", /Bekanntmachung_Stichwahl_OB.pdf$/);
    await expect(page.getByRole("slider")).toHaveCount(0);
    await expect(page.getByRole("checkbox")).toHaveCount(0);
  });

  test("ein Serverfehler bleibt von einem ungültigen Link unterscheidbar", async ({ page }) => {
    await analyseMock(page, true);
    await page.goto(URL);
    await expect(page.getByRole("main").getByRole("alert")).toContainText("konnte nicht geladen werden");
    await expect(page.getByTestId("analyse-fehlt")).toHaveCount(0);
    await analyseMock(page);
    await page.getByRole("button", { name: "Erneut versuchen" }).click();
    await expect(page.getByTestId("analyse-tafel")).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  });

  test("Erklärungen bleiben bei schmalem Fenster und großer Schrift lesbar", async ({ page }) => {
    await analyseMock(page);
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(URL);
      await expect(page.getByTestId("analyse-tafel")).toBeVisible();
      await page.getByTestId("historie-2014").getByText("Stimmenzahlen und Wachstum beider Kandidaten", { exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
    }
    await page.evaluate(() => document.documentElement.style.fontSize = "200%");
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
    // Zahlen dürfen auch bei großer Schrift nicht ziffernweise umbrechen.
    const stimmen = page.getByTestId("kandidaten-ergebnis").getByRole("cell", { name: "25.850", exact: true });
    expect(await stimmen.evaluate((cell) => {
      const range = document.createRange();
      range.selectNodeContents(cell);
      return range.getClientRects().length;
    })).toBe(1);
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await expect(page.locator("#wahlbeteiligung")).toContainText("49.522");
  });
});
