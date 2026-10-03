/**
 * Die Karte „Aus der Geschäftsordnung" unter einer Verfahrensfrage.
 *
 * Der Antwort-Strom ist gestubbt — geprüft wird die Karte, nicht das Modell.
 * Ihr Inhalt ist eine Abschrift aus dem Backend
 * (`fixtures/geschaeftsordnung-karte.json`, erzeugt aus
 * `council/rules_of_procedure.py::card`; `tests/test_browsertest_fixtures.py`
 * hält ihre Felder gleich), der Antworttext ist eine echte Antwort aus der
 * Messung vom 03.10.2026. Festgehalten wird, was die Karte zum Beleg macht:
 * der Paragraf mit Sprung auf seine Seite im PDF, der Wortlaut zum
 * Aufklappen, die Fassung mit Wahlperiode — und dass eine Antwort ohne
 * Beschluss-Treffer nicht als „nichts gefunden" gilt.
 */
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { zustandsDatei } from "./konten";

const KARTE = JSON.parse(readFileSync(join(__dirname, "fixtures", "geschaeftsordnung-karte.json"), "utf-8"));
const FRAGE = "Wie oft darf man im Ausschuss zu einem Punkt sprechen?";
const ANTWORT = "Im Ausschuss dürfen Sie zu einem Punkt mehrfach sprechen: Die Einmal-Regel "
  + "für Ratsdebatten gilt dort ausdrücklich nicht (§ 32 Abs. 1 der Geschäftsordnung). "
  + "Eine feste Höchstzahl nennt die Geschäftsordnung nicht.";

const SSE = [
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "sources", sources: [], question: FRAGE,
    evidence_level: "solide", rules_of_procedure: KARTE })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: ANTWORT })}\n\n`,
  `data: ${JSON.stringify({ type: "done", cited: [], records_state: null })}\n\n`,
].join("");

test.describe("Geschäftsordnung unter der Antwort", () => {
  test.use({ storageState: zustandsDatei("admin") });

  test("zeigt Paragrafen, Wortlaut und Fassung", async ({ page }) => {
    await page.route("**/api/council/ask", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE }),
    );
    await page.goto("/fragen");
    await page.getByPlaceholder(/Deine Frage/).fill(FRAGE);
    await page.keyboard.press("Enter");
    await expect(page.getByText(/Im Ausschuss dürfen Sie/)).toBeVisible();
    await page.getByRole("button", { name: "Weiter" }).click({ timeout: 5_000 }).catch(() => {});

    const karte = page.locator("div.border-dashed", { hasText: "Aus der Geschäftsordnung des Rates" })
      .filter({ visible: true }).first();
    await expect(karte).toBeVisible();
    // Der Paragraf springt auf SEINE Seite im PDF der Stadt.
    const kopf = karte.getByRole("link", { name: /§ 15 Redeordnung, Redezeit/ });
    await expect(kopf).toHaveAttribute("href", /1\.02_20210719\.pdf#page=7$/);
    await expect(karte.getByRole("link", { name: /§ 32 Sonstige Verfahrensvorschriften/ }))
      .toHaveAttribute("href", /#page=15$/);
    // Fassung und Wahlperiode stehen dabei — eine Regel gilt nicht ewig.
    await expect(karte).toContainText("gilt für die Wahlperiode 2021–2026");
    // Der lange Paragraf beginnt als Vorschau und lässt sich aufklappen.
    const mehr = karte.getByRole("button", { name: "Ganzen Wortlaut lesen" }).first();
    await expect(mehr).toHaveAttribute("aria-expanded", "false");
    await mehr.click();
    await expect(karte.getByRole("button", { name: "Weniger anzeigen" }).first())
      .toHaveAttribute("aria-expanded", "true");
    await expect(karte).toContainText("bis zu fünf Minuten");

    // Ohne Beschluss-Treffer ist das trotzdem eine belegte Antwort: kein
    // „Als Thema anlegen", und die Fußzeile nennt die Geschäftsordnung. Ein
    // Thema „Redezeit" meldete sich nie — also auch kein „Daraus ein Thema
    // machen".
    await expect(page.getByText(/Als Thema anlegen/)).toHaveCount(0);
    await expect(page.getByText(/Daraus ein Thema machen/)).toHaveCount(0);
    await expect(page.getByText(/Automatische Antwort aus der Geschäftsordnung des Rates/))
      .toBeVisible();
  });
});
