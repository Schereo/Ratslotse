/**
 * Dashboard: onboarding checklist, quick-access tiles, status badges.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin } from "./helpers";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
    await page.goto("/dashboard");
  });

  test("shows Willkommen headline and email", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Moin!" })).toBeVisible();
    // Email appears in sidebar AND page header — scope to the <main> content area
    await expect(page.locator("main").getByText("admin@test.de").first()).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-dashboard.png", fullPage: true });
  });

  test("onboarding checklist is visible and shows progress", async ({ page }) => {
    await expect(page.getByText("Erste Schritte mit Lotti")).toBeVisible();
    // Fortschrittszähler „n/6" neben dem Balken
    await expect(page.getByText(/\d\/6/)).toBeVisible();
    // Erster Schritt ist verlinkt
    await expect(page.getByRole("link", { name: /Stell dem Rat eine Frage/ })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-onboarding.png", fullPage: true });
  });

  test("quick-access tiles are all visible", async ({ page }) => {
    // Sidebar nav has the same labels — scope to <main> to get the tile headings only
    const main = page.locator("main");
    await expect(main.getByRole("heading", { name: "Ratsinformationssystem" })).toBeVisible();
    await expect(main.getByRole("heading", { name: "Meine Themen" })).toBeVisible();
  });

  test("clicking Ratsinformationssystem tile navigates to /council", async ({ page }) => {
    await page.locator("main").getByRole("link", { name: /Ratsinformationssystem/ }).first().click();
    await page.waitForURL("/council");
    await page.screenshot({ path: "test-results/screenshots/02-tile-navigation.png", fullPage: true });
  });

  test("mobile bottom nav is visible on small viewport", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard");
    // Bottom nav has Start link
    await expect(page.locator("nav[aria-label='Hauptnavigation']")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-mobile-nav.png", fullPage: true });
  });
});
