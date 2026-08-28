import { expect, test } from "@playwright/test";
import { VORSCHAU_PROBLEME } from "../../lib/probleme";

const response = { problems: VORSCHAU_PROBLEME, total: VORSCHAU_PROBLEME.length };

test.describe("Öffentliche Problemkarte", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/probleme", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response),
    }));
  });

  test("zeigt freigegebene Aggregate ohne Anmeldung und filtert sie", async ({ page }) => {
    await page.goto("/probleme");

    await expect(page.getByRole("heading", { name: "Oldenburgs Problemkarte" })).toBeVisible();
    await expect(page.getByText("Unabhängiges Bürgerprojekt")).toBeVisible();
    await expect(page.locator(".problem-map-pin")).toHaveCount(3);
    await expect(page.getByRole("button", { name: /Beispiel: Dunkler Fußweg/ })).toBeVisible();
    await expect(page.getByText("Du willst später selbst etwas melden?")).toBeVisible();

    await page.getByLabel("Nach Status filtern").selectOption("verified");
    await expect(page.getByText("1 sichtbar")).toBeVisible();
    await expect(page.getByRole("button", { name: /Beispiel: Fahrradständer/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Beispiel: Dunkler Fußweg/ })).toBeHidden();
  });

  test("Auswahl ist verlinkbar", async ({ page }) => {
    await page.goto("/probleme");
    await page.getByRole("button", { name: /Beispiel: Barrierefreier Zugang/ }).click();
    await expect(page).toHaveURL(/problem=9003/);
    await expect(page.getByRole("heading", { name: "Beispiel: Barrierefreier Zugang zur Haltestelle fehlt" })).toBeVisible();
  });
});
