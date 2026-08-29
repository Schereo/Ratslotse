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

  test("startet minimal mit der Karte und wechselt ins Status-Board", async ({ page }) => {
    await page.goto("/probleme");

    await expect(page.getByRole("heading", { name: "Oldenburgs Problemkarte" })).toBeVisible();
    await expect(page.locator(".problem-map-pin")).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Karte" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("Du willst später selbst etwas melden?")).toBeVisible();

    await page.getByRole("button", { name: "Status" }).click();
    await expect(page).toHaveURL(/view=status/);
    await expect(page.getByRole("heading", { name: "Neu" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Geprüft" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Beispiel: Fahrradständer/ })).toBeVisible();

    await page.getByLabel("Nach Thema filtern").selectOption("accessibility");
    await expect(page.getByRole("button", { name: /Beispiel: Barrierefreier Zugang/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Beispiel: Fahrradständer/ })).toBeHidden();
  });

  test("Auswahl im Status-Board ist verlinkbar", async ({ page }) => {
    await page.goto("/probleme?view=status");
    await page.getByRole("button", { name: /Beispiel: Barrierefreier Zugang/ }).click();
    await expect(page).toHaveURL(/problem=9003/);
    await expect(page.getByRole("heading", { level: 2, name: "Beispiel: Barrierefreier Zugang zur Haltestelle fehlt" })).toBeVisible();
  });
});
