import { expect, test, type Locator, type Page } from "@playwright/test";
import { zustandsDatei } from "./konten";

// Echter langer Titel aus dem Ratsdaten-Abzug vom 06.09.2026. Die Antworten
// kommen aus der Fixture, damit auch die leere CI-Datenbank genügt.
const TITEL = "Außerplanmäßige Bewilligung einer Verpflichtungsermächtigung in Höhe von 735.000 Euro für das Projekt Kunstrasenplatz/Freizeitanlage Ofenerdiek";
const QUELLE = {
  id: 9382, title: TITEL, committee: "Allgemeine Angelegenheiten",
  session_date: "2026-06-29", outcome: "accepted", kind: "official_text",
};

/** Jede Textzeile muss in ihrem eigenen Kasten liegen. textContent allein
 * würde auch bei Ellipse, line-clamp und abgeschnittenem Überlauf bestehen. */
async function vollstaendig(locator: Locator) {
  const befund = await locator.evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const box = element.getBoundingClientRect();
    const zeilen = Array.from(range.getClientRects());
    return {
      zeilen: zeilen.length,
      abgeschnitten: zeilen.some((r) => r.left < box.left - 1 || r.right > box.right + 1
        || r.top < box.top - 1 || r.bottom > box.bottom + 1),
    };
  });
  expect(befund.zeilen).toBeGreaterThan(0);
  expect(befund.abgeschnitten).toBe(false);
}

async function keineUeberbreite(page: Page) {
  const befund = await page.evaluate(() => ({
    ueberbreite: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    elemente: Array.from(document.querySelectorAll("main *"))
      .filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
      .slice(-5).map((el) => `${el.tagName}.${el.className}: ${el.textContent?.slice(0, 50)}`),
  }));
  expect(befund.ueberbreite, befund.elemente.join("\n")).toBeLessThanOrEqual(1);
}

for (const variante of [
  { name: "Desktop hell", width: 1280, dark: false, schrift: 1 },
  { name: "Handy dunkel", width: 390, dark: true, schrift: 1 },
  { name: "Handy mit doppelter Schrift", width: 390, dark: false, schrift: 2 },
  { name: "Kleines Handy dunkel", width: 320, dark: true, schrift: 1 },
]) {
  test.describe(variante.name, () => {
    test.use({ storageState: zustandsDatei("nutzerin"), viewport: { width: variante.width, height: 844 } });

    test.beforeEach(async ({ page }) => {
      await page.addInitScript((dark) => localStorage.setItem("theme", dark ? "dark" : "light"), variante.dark);
      // Abzeichen sind eine unabhängige Oberfläche und verdecken sonst die
      // Quellen direkt nach der ersten Frage.
      await page.route("**/api/badges**", (route) => route.fulfill({ json: { badges: [], newly_earned: [], earned_count: 0, total: 0 } }));
    });

    test("Stichwörter lassen auf dem Handy Platz für den Inhalt", async ({ page }) => {
      await page.route("**/api/council/decision/8679", (route) => route.fulfill({ json: {
        decision: {
          id: 8679, ksinr: null, title: "Stadionneubau – Übernahme einer Ausfallbürgschaft",
          kind: "decision", outcome: "accepted", committee: "Rat", session_date: "2025-12-15",
          factions: [], parties: [], policy_field: "kultur_sport",
          policy_tags: ["Stadionneubau", "Ausfallbürgschaft", "Darlehen"],
        },
        attendance: [], present_parties: [], sub_votes: [], template_journey: [], similar: [],
        entities: [
          { slug: "stadion-oldenburg", name: "Stadion Oldenburg" },
          { slug: "stadionneubau-maastrichter-strasse", name: "Stadionneubau Maastrichter Straße" },
        ],
      } }));
      await page.goto("/council/decision?id=8679");
      const stichwoerter = page.getByRole("button", { name: "6 Stichwörter", exact: true });
      const thema = page.getByRole("link", { name: "Stadionneubau Maastrichter Straße", exact: true });
      await expect(page.getByRole("heading", { name: /Stadionneubau/ })).toBeVisible();
      await page.addStyleTag({ content: `html { font-size: ${variante.schrift * 100}% !important; }` });
      if (variante.width < 640) {
        await expect(stichwoerter).toHaveAttribute("aria-expanded", "false");
        await expect(thema).toBeHidden();
        await stichwoerter.click();
        await expect(stichwoerter).toHaveAttribute("aria-expanded", "true");
      } else {
        await expect(stichwoerter).toBeHidden();
      }
      await expect(thema).toBeVisible();
      await expect(thema).toHaveAttribute("href", /stadionneubau-maastrichter-strasse/);
      await vollstaendig(thema.locator("span"));
      await expect(page.getByText("Ausfallbürgschaft", { exact: true })).toBeVisible();
      await expect(page.getByText("Darlehen", { exact: true })).toBeVisible();
      await keineUeberbreite(page);
      if (variante.width < 640) {
        await stichwoerter.click();
        await expect(thema).toBeHidden();
      }
    });

    test("Quellentitel und Metadaten bleiben vollständig lesbar", async ({ page }) => {
      const stream = [
        { type: "sources", sources: [QUELLE], question: "Was wurde in Ofenerdiek beschlossen?" },
        { type: "token", text: "Für das Projekt wurde eine Verpflichtungsermächtigung über 735.000 Euro bewilligt. [9382]" },
        { type: "done", cited: [9382] },
      ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
      await page.route("**/api/council/ask", (route) => route.fulfill({ contentType: "text/event-stream", body: stream }));
      await page.goto("/fragen");
      await page.getByPlaceholder(/Deine Frage/).fill("Was wurde in Ofenerdiek beschlossen?");
      await page.keyboard.press("Enter");
      const quelle = page.locator('[id^="qa-"]').getByText(TITEL, { exact: true }).filter({ visible: true }).first();
      await expect(quelle).toBeVisible();
      await page.addStyleTag({ content: `html { font-size: ${variante.schrift * 100}% !important; }` });
      await vollstaendig(quelle);
      await expect(quelle).toHaveCSS("font-size", `${16 * variante.schrift}px`);
      const meta = quelle.locator("..").getByText("Allgemeine Angelegenheiten · 29.06.2026", { exact: true });
      await vollstaendig(meta);
      await keineUeberbreite(page);
    });

    test("Verarbeitungshinweis und beide Auswahlknöpfe bleiben erreichbar", async ({ page }) => {
      await page.route("**/api/council/conversations?*", (route) => route.fulfill({ json: {
        saves_conversations: null, conversations: [], total: 0, matches: 0, has_more: false,
      } }));
      await page.goto("/fragen");
      const hinweis = page.getByText("Frage und passende Ratsauszüge werden über OpenRouter extern verarbeitet;", { exact: false });
      await expect(hinweis).toBeVisible();
      await page.addStyleTag({ content: `html { font-size: ${variante.schrift * 100}% !important; }` });
      await vollstaendig(hinweis);
      await expect(hinweis).toHaveCSS("font-size", `${14 * variante.schrift}px`);
      for (const name of ["KI nutzen & merken", "KI nutzen, nicht merken"]) {
        const knopf = page.getByRole("button", { name, exact: true });
        await vollstaendig(knopf);
        await knopf.scrollIntoViewIfNeeded();
        await expect(knopf).toBeInViewport();
        await knopf.click({ trial: true });
      }
      await keineUeberbreite(page);
    });
  });
}
