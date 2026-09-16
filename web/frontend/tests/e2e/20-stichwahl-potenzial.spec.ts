/**
 * Das Wähler*innen-Potenzial für die Stichwahl (`/stichwahl/potenzial?k=…`,
 * docs/plan-stichwahl-potenzial.md P2) — das Wahlkampf-Werkzeug, das es nur
 * mit Link gibt.
 *
 * Der Endpunkt hängt an `WAHLKAMPF_TOKEN` in der `.env` des Servers; in der
 * CI ist der nicht gesetzt, also antwortet das Backend dort immer 404. Die
 * Antwort wird deshalb gemockt — mit der Abschrift aus `potential.compute()`
 * (`tests/test_browsertest_fixtures.py` hält sie am Vertrag). Erzeugt mit:
 *
 *     FEATURE_FLAGS=wahlabend WAHLKAMPF_TOKEN=probe-token-fuer-die-browsertests \
 *       .venv/bin/python -c "import sys, json; sys.path.insert(0, 'web/backend'); \
 *       from app.routers import wahlabend as r; print(json.dumps(r.stichwahl_potenzial( \
 *       token='probe-token-fuer-die-browsertests', boldt=None, kuessner=None, butzin=None, \
 *       froehlich=None, wilkens=None, cdu=None, turnout_rohr=100, turnout_prange=100, \
 *       turnout_pool=100), ensure_ascii=False))" \
 *       > web/frontend/tests/e2e/fixtures/stichwahl-potenzial-probe.json
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const POTENZIAL = JSON.parse(readFileSync(path.join(__dirname, "fixtures", "stichwahl-potenzial-probe.json"), "utf8"));
const TOKEN = "probe-token-fuer-die-browsertests";

/** Der Endpunkt: mit dem richtigen Token die Abschrift, sonst 404 — genau
 *  wie das Backend. Gibt die gestellten Adressen zurück, damit ein Test
 *  sehen kann, welche Regler die Seite mitschickt. */
async function potenzialMock(page: Page): Promise<string[]> {
  const anfragen: string[] = [];
  await page.route("**/api/wahlabend/stichwahl/potenzial*", (route) => {
    const url = route.request().url();
    anfragen.push(url);
    if (!url.includes(`token=${TOKEN}`)) {
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not Found" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(POTENZIAL) });
  });
  return anfragen;
}

test.describe("Stichwahl-Potenzial", () => {
  test("ohne oder mit falschem Token gibt es die Seite nicht", async ({ page }) => {
    const anfragen = await potenzialMock(page);
    await page.goto("/stichwahl/potenzial");
    await expect(page.getByTestId("potenzial-fehlt")).toBeVisible();
    // Ohne Token wird gar nicht erst gefragt.
    expect(anfragen).toHaveLength(0);
    await page.goto("/stichwahl/potenzial?k=falsch-und-lang-genug-1234");
    await expect(page.getByTestId("potenzial-fehlt")).toBeVisible();
    await expect.poll(() => anfragen.length).toBeGreaterThan(0);
    await expect(page.getByTestId("potenzial-tafel")).toHaveCount(0);
  });

  test("mit Token: Tafel, Regler, Karte, Einsatzliste mit Haken", async ({ page }) => {
    const anfragen = await potenzialMock(page);
    await page.goto(`/stichwahl/potenzial?k=${TOKEN}`);

    // Die Tafel: der Rückstand aus dem ersten Wahlgang und der Saldo mit den Vorgaben.
    const tafel = page.getByTestId("potenzial-tafel");
    await expect(tafel).toContainText("2.225");
    await expect(tafel).toContainText(/Rohr läge [\d.]+ Stimmen vorn/);

    // Ein Regler schickt seinen Stand an den Server — nur den, der abweicht.
    await page.getByLabel("Boldt zu Rohr").fill("80");
    await expect.poll(() => anfragen.some((u) => u.includes("boldt=80%2C15"))).toBe(true);
    expect(anfragen.at(-1)).not.toContain("kuessner=");

    // Die Karte: 91 Urnenbezirke, ein Tipp öffnet die Bezirkstafel.
    const karte = page.getByTestId("potenzial-karte");
    await expect.poll(() => karte.locator("svg path").count()).toBe(91);
    await karte.locator("svg path").first().click({ force: true });
    await expect(page.getByTestId("potenzial-bezirk")).toContainText("Wahlberechtigte");
    await karte.getByRole("button", { name: "Ertrag je Tür" }).click();
    await expect(karte).toContainText("je 1.000 Wahlberechtigte");

    // Die Einsatzliste: Eversten zuoberst; ein Haken überlebt das Neuladen.
    const liste = page.getByTestId("einsatzliste");
    const erstes = liste.locator("[data-buendel]").first();
    await expect(erstes).toContainText("Eversten");
    await erstes.getByRole("button").first().click();
    const haken = liste.getByRole("checkbox").first();
    await haken.check();
    await expect(haken).toBeChecked();
    await page.reload();
    await liste.locator("[data-buendel]").first().getByRole("button").first().click();
    await expect(liste.getByRole("checkbox").first()).toBeChecked();
  });
});
