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

/** Der Schalter kommt aus `/api/app-config`; ohne ihn gibt es keinen Knopf.
 *
 *  **Der try/catch ist nicht Vorsicht, sondern gemessen** (CI, 21.09.2026):
 *  Beendet ein `test.skip()` den Test, während dieser Handler noch auf die
 *  echte Antwort wartet, wirft Playwright „Response has been disposed" — und
 *  zwar in JEDEM danach laufenden Test derselben Datei, weil die Route
 *  weiterhin registriert ist. Ein Handler, der den Fehler schluckt und die
 *  Anfrage durchlässt, macht die ganze Datei gegen diesen Abbruch immun.
 */
async function schalterAn(page: Page, an = true) {
  await page.route("**/api/app-config", async (route) => {
    try {
      const antwort = await route.fetch();
      const body = await antwort.json();
      const features: string[] = (body.features ?? []).filter((f: string) => f !== "lotti-assistentin");
      if (an) features.push("lotti-assistentin");
      await route.fulfill({ json: { ...body, features } });
    } catch {
      await route.fallback().catch(() => { /* der Test ist schon zu Ende */ });
    }
  });
}

async function stromStubben(page: Page, opts: { next?: string | null } = {}) {
  await page.route("**/api/council/explain", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM(opts) })
      .catch(() => { /* der Test ist schon zu Ende */ }),
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

  test("eine Archivfrage wird IM Fenster beantwortet — mit Belegen", async ({ page }) => {
    // Bis PR 4 führte der Knopf weg auf `/fragen`, und der Zusammenhang war
    // hin: Wer auf der Schulden-Seite „wer hat das beantragt?" fragt, landete
    // auf einer leeren Fragen-Seite, und das „das" war weg.
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/ask", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({
        status: 200, contentType: "text/event-stream",
        body: [
          `data: ${JSON.stringify({ type: "sources", sources: [
            { id: 8525, title: "Stadionneubau Maastrichter Straße", committee: "Rat",
              session_date: "2026-06-01" },
          ] })}\n\n`,
          `data: ${JSON.stringify({ type: "token", text: "Der Rat hat 2026 zugestimmt." })}\n\n`,
          `data: ${JSON.stringify({ type: "done", cited: [8525] })}\n\n`,
        ].join(""),
      }).catch(() => { /* Test ist schon zu Ende */ });
    });
    await stromStubben(page, { next: "ratsfrage" });
    await page.goto("/dashboard");
    await knopf(page).click();
    await fenster(page).getByLabel("Frage an Lotti").fill("Wer hat dagegen gestimmt?");
    await fenster(page).getByRole("button", { name: "Fragen" }).click();
    await fenster(page).getByRole("button", { name: /Den Rat fragen/ }).click();
    await expect(fenster(page).getByText("Der Rat hat 2026 zugestimmt.")).toBeVisible();
    await expect(fenster(page).getByText("Stadionneubau Maastrichter Straße")).toBeVisible();
    // Der Bildschirm reist mit — sonst sucht das Archiv nach nichts.
    const screen = (geschickt as { screen?: { route?: string } })?.screen;
    expect(screen?.route).toBe("/dashboard");
    // Und der Weg ins volle Ratsgespräch steht darunter.
    await expect(fenster(page).getByRole("button", { name: /Im Ratsgespräch weiterführen/ }))
      .toBeVisible();
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

  test("der Erklär-Modus sagt in jedem Fall, woran man ist", async ({ page }) => {
    // **Die CI-Ratsdatenbank ist LEER**, und der Haushalt zeigt ohne Daten
    // keine Bühne (Designsprache: „Ohne Datengrundlage entfällt die Bühne")
    // — also auch keine Anker. Geprüft wird deshalb eine Zusage, die in
    // beiden Welten gilt: Entweder es gibt Abzeichen, oder der Modus sagt
    // ehrlich, dass er hier nichts einzeln erklären kann. Der zweite Zweig
    // ist kein Notbehelf, sondern der Fall, den jemand mit leerer Seite
    // wirklich sieht.
    await page.goto("/haushalt/schulden");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    // Der Modus schließt das Fenster: Die Abzeichen stehen auf der SEITE,
    // und auf dem Handy deckt das Fenster genau sie ab.
    await expect(fenster(page)).toBeHidden();
    const marken = page.locator("[data-erklaer-marke]");
    const hinweis = page.getByText(/nichts einzeln erklären/);
    await expect(marken.first().or(hinweis)).toBeVisible();
  });

  test("ein angetipptes Abzeichen schickt NUR diesen Baustein", async ({ page }) => {
    let geschickt: Record<string, unknown> | null = null;
    await page.route("**/api/council/explain", async (route) => {
      geschickt = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM() });
    });
    await page.goto("/haushalt/schulden");
    // ERST die Daten abwarten, dann den Modus starten: Sonst entscheidet ein
    // Rennen zwischen Nachladen und Messen, ob es Anker gibt — und der Test
    // übersprang sich auch dort, wo Daten da waren.
    await page.waitForLoadState("networkidle");
    const anker = page.locator("[data-erklaer]");
    // Ohne Ratsdaten (so läuft die CI) gibt es keinen Baustein zum Antippen —
    // sichtbar überspringen statt etwas anderes messen.
    test.skip(await anker.count() === 0,
      "Diese Datenbank hat keine Haushaltsdaten — also auch keine Anker.");
    await knopf(page).click();
    await fenster(page).getByRole("button", { name: "Etwas auf der Seite zeigen" }).click();
    const marken = page.locator("[data-erklaer-marke]");
    await expect(marken.first()).toBeVisible();
    await marken.first().click();
    await expect(fenster(page).getByText(ANTWORT)).toBeVisible();
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
    const marken = page.locator("[data-erklaer-marke]");
    // Egal ob Anker oder Hinweis — eines von beiden steht da, bevor Esc kommt.
    await page.getByText(/nichts einzeln erklären/).or(marken.first()).first().waitFor();
    await page.keyboard.press("Escape");
    await expect(marken).toHaveCount(0);
    await expect(page.getByText(/nichts einzeln erklären/)).toBeHidden();
  });

  test("ohne beantwortete Einwilligung fragt Lotti nichts", async ({ page }) => {
    // Die Saat-Konten haben die Frage längst beantwortet — für diesen Fall
    // muss sie zurückgesetzt werden. Geprüft wird die Zusage, die dahinter
    // steht: Der Satz über die externe Verarbeitung steht VOR der ersten
    // Frage, nicht danach.
    await page.route("**/api/auth/me", async (route) => {
      try {
        const antwort = await route.fetch();
        const body = await antwort.json();
        await route.fulfill({ json: { ...body, saves_conversations: null } });
      } catch {
        await route.fallback().catch(() => { /* Test ist schon zu Ende */ });
      }
    });
    await page.goto("/dashboard");
    await knopf(page).click();
    await expect(fenster(page).getByText(/Soll ich mir deine Gespräche merken/)).toBeVisible();
    await expect(fenster(page).getByText(/OpenRouter/)).toBeVisible();
    await expect(fenster(page).getByRole("button", { name: "Fragen" })).toBeDisabled();
    await expect(fenster(page).getByRole("button", { name: "Was sehe ich hier?" })).toBeDisabled();
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
