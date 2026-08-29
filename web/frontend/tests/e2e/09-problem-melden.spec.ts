import { expect, test } from "@playwright/test";

test.describe("Private Problemmeldung", () => {
  test("bleibt bei ausgefallenem öffentlichen Vergleich nutzbar", async ({ page }) => {
    const registered = await page.request.post("/api/auth/register", {
      data: { email: "vergleich@test.de", password: "password123" },
    });
    expect(registered.status()).toBe(201);
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "temporär nicht erreichbar" }),
    }));

    await page.goto("/probleme/melden");
    await page.locator("#report-location-label").fill("Theaterwall");
    await page.getByRole("button", { name: "Kartenmitte markieren" }).click();

    await expect(page.getByText(/private Meldung ist davon nicht betroffen/i)).toBeVisible();
    const next = page.getByRole("button", { name: /Weiter/ });
    await expect(next).toBeEnabled();
    await next.click();
    await expect(page.getByRole("heading", { name: "Was hast du beobachtet?" })).toBeVisible();
  });

  test("fragt mit der optionalen KI-Schreibhilfe nach und übernimmt einen Entwurf", async ({ page }) => {
    const registered = await page.request.post("/api/auth/register", {
      data: { email: "schreibhilfe@test.de", password: "password123" },
    });
    expect(registered.status()).toBe(201);
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
          redacted: false,
        } : {
          kind: "ready",
          question: null,
          draft_text: "Der Zugang ist durch eine hohe Kante nicht stufenlos nutzbar. Die Barriere besteht täglich und verhindert die selbstständige Nutzung mit einem Rollstuhl.",
          redacted: false,
        }),
      });
    });

    await page.goto("/probleme/melden");
    await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
    await page.getByRole("button", { name: "Kein passendes Problem dabei" }).click();
    await page.getByRole("button", { name: /Weiter/ }).click();
    await page.locator("#report-category").selectOption("accessibility");
    await page.getByRole("checkbox", { name: /optionale externe KI-Schreibhilfe nutzen/i }).check();
    await page.getByRole("button", { name: /Geführt starten/ }).click();
    await page.locator("#report-assistant-answer").fill("Eine hohe Kante verhindert den Zugang mit einem Rollstuhl.");
    await page.getByRole("button", { name: "Antwort senden" }).click();
    await expect(page.getByText("Wie häufig tritt diese Barriere auf?")).toBeVisible();
    await page.locator("#report-assistant-answer").fill("Die Kante blockiert den Zugang jeden Tag.");
    await page.getByRole("button", { name: "Antwort senden" }).click();

    await expect(page.getByText(/Entwurf ist übernommen/)).toBeVisible();
    await expect(page.locator("#report-text")).toHaveValue(/Der Zugang ist durch eine hohe Kante/);
    expect(calls).toBe(2);
  });

  test("führt ein verifiziertes Konto bis zur privaten Einreichung", async ({ page }) => {
    const registered = await page.request.post("/api/auth/register", {
      data: { email: "meldung@test.de", password: "password123" },
    });
    expect(registered.status()).toBe(201);
    await page.goto("/probleme/melden");

    await expect(page.getByRole("heading", { name: "Problem melden" })).toBeVisible();
    await expect(page.locator('input[type="file"]')).toHaveCount(0);
    await page.locator("#report-location-label").fill("Theaterwall");
    const map = page.getByLabel("Ungefähre Lage der Meldung auswählen");
    await map.focus();
    await map.press("ArrowRight");
    await page.getByRole("button", { name: "Kartenmitte markieren" }).click();
    await expect(page.getByText("Lage markiert")).toBeVisible();
    await page.getByRole("button", { name: /Ganz Oldenburg/ }).click();
    await page.getByRole("button", { name: "Kein passendes Problem dabei" }).click();
    await page.getByRole("button", { name: /Weiter/ }).click();

    await page.locator("#report-category").selectOption("childcare");
    await page.locator("#report-category-detail").fill(
      "Betreuungsplätze fehlen werktags über den gesamten Tag.",
    );
    await page.locator("#report-text").fill(
      "In mehreren Stadtteilen fehlen ausreichend Betreuungsplätze für Kinder.",
    );
    await page.getByRole("button", { name: /Weiter/ }).click();

    await expect(page.getByText("Ganz Oldenburg")).toBeVisible();
    await page.getByRole("link", { name: "Datenschutz" }).click();
    await expect(page.getByRole("heading", { name: "Datenschutzerklärung" })).toBeVisible();
    await page.goBack();
    await expect(page.getByRole("heading", { name: "Kurz prüfen und absenden" })).toBeVisible();
    await expect(page.locator("#report-confirmed-text")).toHaveValue(
      "In mehreren Stadtteilen fehlen ausreichend Betreuungsplätze für Kinder.",
    );
    await page.getByRole("checkbox").check();
    await page.locator("#report-confirmed-text").fill(
      "In mehreren Stadtteilen fehlen dauerhaft ausreichend Betreuungsplätze für Kinder.",
    );
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Privat absenden" }).click();

    await expect(page.getByRole("heading", { name: "Meldung privat eingegangen" })).toBeVisible();
    await expect(page.getByText(/noch nicht öffentlich/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Zur Problemkarte" })).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("ratslotse:private-problemmeldung"))).toBeNull();
  });
});
