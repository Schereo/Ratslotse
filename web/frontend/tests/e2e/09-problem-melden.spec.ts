import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function register(page: Page, email: string) {
  const response = await page.request.post("/api/auth/register", {
    data: { email, password: "password123" },
  });
  expect(response.status()).toBe(201);
}

async function reachChat(page: Page) {
  await page.goto("/probleme/melden");
  await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
  await page.getByRole("button", { name: "Neue Meldung fortsetzen" }).click();
  await page.getByRole("button", { name: "Datum übernehmen" }).click();
  await page.getByRole("checkbox", { name: /externen KI-Melde-Chat nutzen/i }).check();
  await page.getByRole("button", { name: "Gespräch starten" }).click();
}

test.describe("Privater KI-Melde-Chat", () => {
  test("blockiert bei ausgefallenem öffentlichen Vergleich die Ortsmeldung nicht", async ({ page }) => {
    await register(page, "vergleich@test.de");
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "temporär nicht erreichbar" }),
    }));

    await page.goto("/probleme/melden");
    await page.getByRole("button", { name: /Ein Ort/ }).click();
    await page.locator("#report-location-label").fill("Theaterwall");
    await page.getByRole("button", { name: "Kartenmitte markieren" }).click();
    await page.getByRole("button", { name: /Ort übernehmen/ }).click();

    await expect(page.getByText(/blockiert deine private Meldung nicht/i)).toBeVisible();
    await page.getByRole("button", { name: "Trotzdem weiter" }).click();
    await expect(page.getByText("Wann hast du das Problem zuletzt selbst beobachtet?")).toBeVisible();
  });

  test("fragt im Chat nach und öffnet erst danach den korrigierbaren Entwurf", async ({ page }) => {
    await register(page, "schreibhilfe@test.de");
    let calls = 0;
    await page.route("**/api/meldungen/assistenz", async (route) => {
      const body = route.request().postDataJSON();
      expect(body).not.toHaveProperty("location_label");
      expect(body).not.toHaveProperty("latitude");
      expect(body).not.toHaveProperty("longitude");
      calls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(calls === 1 ? {
          kind: "question",
          question: "Wie häufig tritt diese Barriere auf?",
          draft_text: null,
          category: null,
          category_detail: null,
          redacted: false,
        } : {
          kind: "ready",
          question: null,
          draft_text: "Der Zugang ist durch eine hohe Kante nicht stufenlos nutzbar. Die Barriere besteht täglich und verhindert die selbstständige Nutzung mit einem Rollstuhl.",
          category: "accessibility",
          category_detail: "Eine hohe Kante verhindert täglich den stufenlosen Zugang.",
          redacted: false,
        }),
      });
    });

    await reachChat(page);
    await expect(page.locator("#report-category")).toHaveCount(0);
    await page.locator("#report-assistant-answer").fill("Eine hohe Kante verhindert den Zugang mit einem Rollstuhl.");
    await page.getByRole("button", { name: "Antwort senden" }).click();
    await expect(page.getByText("Wie häufig tritt diese Barriere auf?")).toBeVisible();
    await page.locator("#report-assistant-answer").fill("Die Kante blockiert den Zugang jeden Tag.");
    await page.getByRole("button", { name: "Antwort senden" }).click();

    await expect(page.getByRole("heading", { name: "Prüfen, korrigieren, freigeben" })).toBeVisible();
    await expect(page.locator("#report-category")).toHaveValue("accessibility");
    await expect(page.locator("#report-confirmed-text")).toHaveValue(/Der Zugang ist durch eine hohe Kante/);
    expect(calls).toBe(2);
  });

  test("lässt den KI-Entwurf korrigieren, bestätigen und genau einmal privat absenden", async ({ page }) => {
    await register(page, "meldung@test.de");
    await page.route("**/api/meldungen/assistenz", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "ready",
        question: null,
        draft_text: "In mehreren Stadtteilen fehlen ausreichend Betreuungsplätze für Kinder. Familien finden werktags keine verlässliche Betreuung.",
        category: "childcare",
        category_detail: "Werktags fehlen verlässliche Betreuungsplätze für Kinder.",
        redacted: false,
      }),
    }));

    await reachChat(page);
    await page.locator("#report-assistant-answer").fill("In mehreren Stadtteilen fehlen werktags Betreuungsplätze für Kinder.");
    await page.getByRole("button", { name: "Antwort senden" }).click();
    await expect(page.getByRole("heading", { name: "Prüfen, korrigieren, freigeben" })).toBeVisible();

    await page.locator("#report-confirmed-text").fill(
      "In mehreren Stadtteilen fehlen dauerhaft ausreichende Betreuungsplätze für Kinder. Familien finden werktags keine verlässliche Betreuung.",
    );
    await page.getByRole("checkbox", { name: /Ort, Einordnung und Meldetext selbst geprüft/i }).check();
    await page.getByRole("button", { name: "Geprüfte Meldung privat absenden" }).click();

    await expect(page.getByRole("heading", { name: "Meldung privat eingegangen" })).toBeVisible();
    await expect(page.getByText(/noch nicht öffentlich/i)).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("ratslotse:private-problemmeldung"))).toBeNull();
  });
});
