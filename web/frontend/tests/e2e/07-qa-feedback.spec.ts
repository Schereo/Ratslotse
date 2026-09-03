/**
 * Daumen-Feedback zur Antwort von „Frag den Rat" (5a/I-03).
 *
 * Der Antwort-Stream ist gestubbt — der Test prüft die Bewertung, nicht das
 * LLM. Kern des Tests ist Tims Befund: Ein einmal gesetzter Daumen runter ließ
 * sich nicht mehr korrigieren, beide Knöpfe waren danach dauerhaft disabled.
 */
import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAdmin, gespraecheNichtMerken } from "./helpers";

/** Anmelden, egal ob das Konto schon existiert: Läuft die ganze Suite, hat
 *  01-auth es angelegt; läuft nur diese Datei, legt sie es selbst an. */
async function anmelden(page: import("@playwright/test").Page) {
  await page.goto("/register");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 8_000 }).catch(() => loginAdmin(page));
}

/** Der /ask-Endpoint spricht SSE — hier die kürzeste Runde, die eine
 *  vollständige Antwort mit Aktionszeile erzeugt. */
const SSE_ANTWORT = [
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "sources", sources: [], question: "Was wurde zum Radverkehr beschlossen?" })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: "Der Rat hat mehrere Fahrradstraßen beschlossen." })}\n\n`,
  `data: ${JSON.stringify({ type: "done" })}\n\n`,
].join("");

test.describe("Daumen-Feedback", () => {
  test("Daumen runter lässt sich in Daumen hoch ändern", async ({ page }) => {
    await anmelden(page);

    await page.route("**/api/council/ask", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_ANTWORT }),
    );
    // Jede Bewertung mitschreiben, statt sie an das echte Backend zu geben.
    const gesendet: string[] = [];
    await page.route("**/api/council/qa-feedback", async (route) => {
      gesendet.push(JSON.parse(route.request().postData() ?? "{}").rating);
      await route.fulfill({ status: 201, contentType: "application/json", body: '{"ok":true}' });
    });

    await gespraecheNichtMerken(page);
    await page.goto("/fragen");
    // Der Platzhalter heißt „Deine Frage …" — „Frag den Rat" steht heute auf
    // dem Knopf des Dashboards, nicht im Eingabefeld.
    await page.getByPlaceholder(/Deine Frage/).fill("Was wurde zum Radverkehr beschlossen?");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Der Rat hat mehrere Fahrradstraßen beschlossen.")).toBeVisible();
    // Das Abzeichen „Erste Frage" legt sich über die Aktionszeile — und es
    // erscheint mit Verzögerung. Eine Sichtprüfung SOFORT nach der Antwort
    // kommt zu früh: Sie meldet „nicht da", und der Daumen darunter bleibt
    // danach unklickbar („visible, enabled and stable", 52 Versuche lang).
    const abzeichen = page.getByRole("button", { name: "Weiter" });
    await abzeichen.click({ timeout: 5_000 }).catch(() => {});
    await expect(abzeichen).toHaveCount(0);

    const hoch = page.getByRole("button", { name: "Antwort war hilfreich" });
    const runter = page.getByRole("button", { name: "Antwort war nicht hilfreich" });

    await runter.click();
    await expect(runter).toHaveAttribute("aria-pressed", "true");
    // Der Grund-Nachtrag darf die Korrektur nicht blockieren.
    await expect(page.getByPlaceholder("Was war falsch? (optional)")).toBeVisible();

    // Der Befund: hier war vorher Schluss.
    await expect(hoch).toBeEnabled();
    await hoch.click();
    await expect(hoch).toHaveAttribute("aria-pressed", "true");
    await expect(runter).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByPlaceholder("Was war falsch? (optional)")).toBeHidden();

    // Nochmal derselbe Daumen sendet nicht erneut (schont das Rate-Limit).
    await hoch.click();
    await expect(page.locator("[data-sonner-toast]")).toContainText(/Bewertung geändert|Rückmeldung/);
    expect(gesendet).toEqual(["down", "up"]);
  });
});
