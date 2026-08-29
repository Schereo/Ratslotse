import { expect, test } from "@playwright/test";

test.describe("Private Problemmeldung", () => {
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
