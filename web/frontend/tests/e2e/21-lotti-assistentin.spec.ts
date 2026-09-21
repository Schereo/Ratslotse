/**
 * Lotti als Assistentin: der schwebende Knopf und sein Fenster.
 *
 * Der Erklär-Strom ist **gestubbt** — geprüft wird die Oberfläche, nicht das
 * Sprachmodell (dafür gibt es `eval/run_assistant.py`). Vier Zusagen, die man
 * einer Komponente nicht ansieht und die alle schon einmal anders waren:
 *
 * 1. Der Knopf ist **überall** da, am Schreibtisch wie auf dem Handy — genau
 *    das war im ersten Entwurf nicht so (er lag mobil in der Kopfleiste).
 * 2. Auf `/fragen` schneidet er den Composer **nicht** an.
 * 3. Der Verlauf **überlebt den Seitenwechsel**; das ist der Grund, warum das
 *    Fenster in der App-Hülle lebt und nicht in einer Seite.
 * 4. Ohne Schalter und auf den Konto-Seiten gibt es ihn **nicht**.
 *
 * Läuft gegen die LEERE Ratsdatenbank der CI: Keine Zusage hier hängt an
 * einem bestimmten Beschluss.
 */
import { expect, test, type Page } from "@playwright/test";

import { zustandsDatei } from "./konten";

const ANTWORT = "Die Treppe zeigt, wie viel die Stadt in jedem Jahr zurückzahlt.";

const STROM = (opts: { next?: string | null } = {}) => [
  `data: ${JSON.stringify({ type: "step", step: "context" })}\n\n`,
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: ANTWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model",
    next: opts.next ?? null, glossary: ["Tilgung"], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Der Schalter kommt aus `/api/app-config`; ohne ihn gibt es keinen Knopf. */
async function schalterAn(page: Page, an = true) {
  await page.route("**/api/app-config", async (route) => {
    const antwort = await route.fetch();
    const body = await antwort.json();
    const features: string[] = (body.features ?? []).filter((f: string) => f !== "lotti-assistentin");
    if (an) features.push("lotti-assistentin");
    await route.fulfill({ json: { ...body, features } });
  });
}

async function stromStubben(page: Page, opts: { next?: string | null } = {}) {
  await page.route("**/api/council/explain", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM(opts) }),
  );
}

const knopf = (page: Page) => page.locator("[data-lotti-knopf]");
const fenster = (page: Page) => page.locator("[data-lotti-fenster]");

test.describe("Lotti-Knopf und -Fenster", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test.beforeEach(async ({ page }) => {
    await schalterAn(page);
    await stromStubben(page);
  });

  test("der Knopf schwebt unten rechts — am Schreibtisch wie auf dem Handy", async ({ page }) => {
    for (const grosse of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(grosse);
      await page.goto("/dashboard");
      await expect(knopf(page)).toBeVisible();
      const box = (await knopf(page).boundingBox())!;
      // Rechte Hälfte, untere Hälfte — mehr soll hier nicht festgenagelt sein
      // (Pixelvergleiche meldet jede beabsichtigte Änderung als Fehler).
      expect(box.x + box.width / 2).toBeGreaterThan(grosse.width / 2);
      expect(box.y + box.height / 2).toBeGreaterThan(grosse.height / 2);
    }
  });

  test("er öffnet das Fenster, wird zum Kreuz, und Esc schließt wieder", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(fenster(page)).toBeHidden();
    await knopf(page).click();
    await expect(fenster(page)).toBeVisible();
    await expect(knopf(page)).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(fenster(page)).toBeHidden();
    // Der Fokus kehrt auf den Knopf zurück — sonst beginnt die nächste
    // Tabulatortaste wieder ganz oben auf der Seite (BITV).
    await expect(knopf(page)).toBeFocused();
  });

  test("„Was sehe ich hier?“ zeigt die Antwort im Fenster", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
  });

  test("bei einer Archivfrage führt der Weg zu „Frag den Rat“", async ({ page }) => {
    await stromStubben(page, { next: "ratsfrage" });
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();
    const weiter = fenster(page).getByRole("button", { name: /Den Rat fragen/ });
    await expect(weiter).toBeVisible();
    await weiter.click();
    // NICHT die Adresse prüfen: Die Fragen-Seite übernimmt `?q=` in den
    // Composer und räumt den Parameter danach weg (Befund F5 dort). Geprüft
    // gehört, was ankommt — die Frage steht im Eingabefeld.
    await expect(page).toHaveURL(/\/fragen/);
    await expect(page.getByPlaceholder(/Deine Frage/).first())
      .toHaveValue("Wer hat dagegen gestimmt?");
  });

  test("der Verlauf überlebt den Seitenwechsel", async ({ page }) => {
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Was sehe ich hier?" }).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
    // Wegnavigieren und wieder öffnen: Das Fenster lebt in der App-Hülle.
    await page.goto("/bookmarks");
    await knopf(page).click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
  });

  test("auf der Fragen-Seite schneidet der Knopf den Composer nicht an", async ({ page }) => {
    for (const grosse of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(grosse);
      await page.goto("/fragen");
      const eingabe = page.getByPlaceholder(/Deine Frage/).first();
      await expect(eingabe).toBeVisible();
      const a = (await knopf(page).boundingBox())!;
      const b = (await eingabe.boundingBox())!;
      const ueberlappt = a.x < b.x + b.width && a.x + a.width > b.x
        && a.y < b.y + b.height && a.y + a.height > b.y;
      expect(ueberlappt, `Knopf überdeckt den Composer bei ${grosse.width} px`).toBe(false);
    }
  });

  test("der Erklär-Modus zeigt Abzeichen und fragt nach dem angetippten Baustein",
    async ({ page }) => {
      let geschickt: Record<string, unknown> | null = null;
      await page.route("**/api/council/explain", async (route) => {
        geschickt = route.request().postDataJSON();
        await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
      });
      await page.goto("/haushalt/schulden");
      await knopf(page).click();
      await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
      // Der Modus schließt das Fenster: Die Abzeichen stehen auf der SEITE,
      // und auf dem Handy deckt das Fenster genau sie ab.
      await expect(fenster(page)).toBeHidden();
      const marken = page.locator("[data-erklaer-marke]");
      await expect(marken.first()).toBeVisible();
      await marken.first().click();
      await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
      // Was mitgeht: NUR dieses Element — nicht die Seite, nicht die Nachbarn.
      expect(geschickt).toBeTruthy();
      const el = (geschickt as { element?: { key?: string; text?: string } }).element!;
      expect(el.key).toMatch(/^haushalt-schulden\./);
      expect(el.text!.length).toBeGreaterThan(0);
      expect(el.text!.length).toBeLessThanOrEqual(1202);
    });

  test("Esc beendet den Erklär-Modus", async ({ page }) => {
    await page.goto("/haushalt/schulden");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    await expect(page.locator("[data-erklaer-marke]").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("[data-erklaer-marke]")).toHaveCount(0);
  });

  test("auf der Konto-Seite gibt es Lotti nicht", async ({ page }) => {
    // Dort stehen die eigene Adresse und die Kontodaten — sie dürfen nicht
    // als Seitentext in einen Prompt wandern (kern/knowledge.py).
    await page.goto("/account");
    await expect(knopf(page)).toBeHidden();
  });

  test("ohne Schalter gibt es keinen Knopf", async ({ page }) => {
    await schalterAn(page, false);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading").first()).toBeVisible();
    await expect(knopf(page)).toBeHidden();
  });
});
