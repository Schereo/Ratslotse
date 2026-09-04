/**
 * Fachwörter im Antworttext von „Frag den Rat".
 *
 * Der Antwort-Stream ist gestubbt — geprüft wird das Unterringeln, nicht das
 * LLM. Der Test hält zwei Dinge fest, die beide schon einmal anders waren:
 * dass ein Fachbegriff im FLIESSTEXT der Antwort seine Erklärung bekommt (das
 * Glossar lag bis 09/2026 nur auf den Haushalts-Seiten), und dass ein Begriff
 * nur bei der ERSTEN Nennung markiert wird — sonst ist eine lange Antwort
 * durchgehend gepunktet.
 */
import { test, expect } from "@playwright/test";
import {
  ADMIN_EMAIL, ADMIN_PASSWORD, einrichtungUeberspringen, gespraecheNichtMerken, loginAdmin,
} from "./helpers";

async function anmelden(page: import("@playwright/test").Page) {
  await page.goto("/register");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 8_000 }).catch(() => loginAdmin(page));
}

// „Ausfallbürgschaft" ist der Anlass: Genau diese Frage hat die KI-Frage am
// 04.09.2026 zweimal verschieden beantwortet. „Bebauungsplan" steht zweimal
// darin — der zweite darf keine Markierung mehr bekommen.
const ANTWORT = "Die Stadt hat eine Ausfallbürgschaft über rund 116,5 Millionen Euro "
  + "übernommen; der Verwaltungsausschuss stimmte zu. Der Bebauungsplan dazu liegt vor. "
  + "Ein Bebauungsplan gilt als Satzung.";

const SSE_ANTWORT = [
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "sources", sources: [], question: "Was ist eine Ausfallbürgschaft?" })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: ANTWORT })}\n\n`,
  `data: ${JSON.stringify({ type: "done" })}\n\n`,
].join("");

test.describe("Glossar im Antworttext", () => {
  test("erklärt Fachbegriffe bei der ersten Nennung", async ({ page }) => {
    await anmelden(page);
    await page.route("**/api/council/ask", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_ANTWORT }),
    );
    await gespraecheNichtMerken(page);
    await einrichtungUeberspringen(page);
    await page.goto("/fragen");
    await page.getByPlaceholder(/Deine Frage/).fill("Was ist eine Ausfallbürgschaft?");
    await page.keyboard.press("Enter");
    await expect(page.getByText(/Die Stadt hat eine/)).toBeVisible();
    // Das Abzeichen „Erste Frage" legt sich als Fläche über die ganze Seite und
    // fängt jeden Zeiger ab — der Begriff darunter ist sichtbar und trotzdem
    // nicht überfahrbar (dieselbe Falle wie in 07-qa-feedback).
    const abzeichen = page.getByRole("button", { name: "Weiter" });
    await abzeichen.click({ timeout: 5_000 }).catch(() => {});
    await expect(abzeichen).toHaveCount(0);

    // Der Begriff aus der Frage trägt seine Erklärung.
    const begriff = page.getByRole("button", { name: "Was bedeutet Ausfallbürgschaft?" });
    await expect(begriff).toBeVisible();
    await begriff.hover();
    await expect(page.getByRole("tooltip")).toContainText(/erst dann zahlt/);

    // Zweimal derselbe Begriff, einmal markiert.
    await expect(page.getByRole("button", { name: "Was bedeutet Bebauungsplan?" })).toHaveCount(1);
  });
});
