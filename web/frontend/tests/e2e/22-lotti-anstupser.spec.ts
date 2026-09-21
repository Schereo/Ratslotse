/**
 * Lotti klopft an — selten, und mit Grenzen, die man sehen kann.
 *
 * Die Grenzen selbst prüft `lib/anstupser.test.ts` (reine Funktion, jede
 * Zeile der Tabelle ein Fall). Hier steht, was man nur im Browser sieht:
 * dass die Uhr wirklich zählt, dass die Blase keinen Fokus stiehlt, dass ein
 * „Ja" das Fenster öffnet und dass sie auf `/fragen` nie erscheint.
 *
 * Gearbeitet wird mit `page.clock` — 45 Sekunden echte Lesezeit je Test wären
 * eine Minute Suite je Fall.
 */
import { expect, test, type Page } from "@playwright/test";

import { zustandsDatei } from "./konten";

const BLASE = "[data-lotti-anstupser]";

async function schalterAn(page: Page, namen: string[]) {
  await page.route("**/api/app-config", async (route) => {
    try {
      const antwort = await route.fetch();
      const body = await antwort.json();
      const features = [...(body.features ?? []).filter(
        (f: string) => !f.startsWith("lotti-")), ...namen];
      await route.fulfill({ json: { ...body, features } });
    } catch {
      await route.fallback().catch(() => { /* Test ist schon zu Ende */ });
    }
  });
}

/** Die Bedingungen erfüllen: dritter Seitenaufruf, gelesen, gerade aktiv.
 *
 *  **Die Reihenfolge ist der Punkt.** Erst die Lesezeit, DANN die
 *  Interaktion: Der Anstupser verlangt beides — 45 Sekunden auf der Seite
 *  UND ein Lebenszeichen in den letzten zehn. Der erste Anlauf dieses Tests
 *  klickte zuerst und ließ dann 50 Sekunden verstreichen; danach schwieg
 *  Lotti völlig zu Recht, denn so sieht ein liegengelassener Tab aus.
 */
async function lesen(page: Page, pfad: string) {
  await page.addInitScript(() => {
    // Zwei Seitenaufrufe „vorher" — die ersten beiden bleiben in Ruhe.
    try { sessionStorage.setItem("ratslotse:lotti-seiten", "2"); } catch { /* egal */ }
  });
  await page.clock.install();
  await page.goto(pfad);
  await page.waitForLoadState("networkidle");
  // **Erst warten, bis Lotti überhaupt da ist.** Der Schalter kommt über
  // `/api/app-config`, also über das Netz; die Uhr des Anstupsers läuft erst
  // ab dem Effekt, der DANACH greift. Wer vorher 46 Sekunden vorspult,
  // verschenkt sie: Die Lesezeit zählt ab null, und die Blase bleibt aus.
  // Genau daran ist der erste Anlauf in der CI gescheitert (#1445) — lokal
  // war der Abruf schnell genug, um es zu verdecken.
  await expect(page.locator("[data-lotti-knopf]")).toBeVisible();
  await page.clock.runFor(46_000);        // gelesen …
  await page.mouse.move(200, 300);        // … und noch da
  await page.mouse.down();
  await page.mouse.up();
  await page.clock.runFor(6_000);         // der Takt prüft alle 5 s
}

test.describe("Lottis Anstupser", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test.beforeEach(async ({ page }) => {
    await schalterAn(page, ["lotti-assistentin", "lotti-anstupser"]);
  });

  test("klopft nach der Lesezeit an — und stiehlt den Fokus nicht", async ({ page }) => {
    await lesen(page, "/haushalt/schulden");
    await expect(page.locator(BLASE)).toBeVisible();
    await expect(page.locator(BLASE)).toContainText("Hast du eine Frage");
    // `role="status"` meldet sich, ohne den Fokus zu nehmen: Wer gerade tippt,
    // soll nicht mitten im Wort woanders landen.
    await expect(page.locator(BLASE)).toHaveAttribute("role", "status");
    const fokus = await page.evaluate(() => document.activeElement?.tagName ?? "");
    expect(fokus).not.toBe("BUTTON");
  });

  test("„Ja“ öffnet das Fenster", async ({ page }) => {
    await lesen(page, "/haushalt/schulden");
    await page.locator(BLASE).getByRole("button", { name: "Ja, frag Lotti" }).click();
    await expect(page.locator("[data-lotti-fenster]")).toBeVisible();
    await expect(page.locator(BLASE)).toBeHidden();
  });

  test("nach einem × ist an diesem Tag Ruhe", async ({ page }) => {
    await lesen(page, "/haushalt/schulden");
    await page.locator(BLASE).getByLabel("Nicht jetzt").click();
    await expect(page.locator(BLASE)).toBeHidden();
    // Dieselbe Seite noch einmal: Der Tages-Deckel hält.
    await page.goto("/haushalt/einnahmen");
    await page.waitForLoadState("networkidle");
    await page.clock.runFor(46_000);
    await page.mouse.move(220, 320);
    await page.mouse.down();
    await page.mouse.up();
    await page.clock.runFor(6_000);
    await expect(page.locator(BLASE)).toBeHidden();
  });

  test("auf der Fragen-Seite klopft sie nie an", async ({ page }) => {
    await lesen(page, "/fragen");
    await expect(page.locator(BLASE)).toBeHidden();
  });

  test("ohne Schalter klopft sie nie an", async ({ page }) => {
    await schalterAn(page, ["lotti-assistentin"]);
    await lesen(page, "/haushalt/schulden");
    await expect(page.locator(BLASE)).toBeHidden();
    // Der Knopf selbst ist davon unberührt — der Anstupser hat einen eigenen
    // Schalter, damit man ihn auf Prod einzeln abstellen kann.
    await expect(page.locator("[data-lotti-knopf]")).toBeVisible();
  });
});
