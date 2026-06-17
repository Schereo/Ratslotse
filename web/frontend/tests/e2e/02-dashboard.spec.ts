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
    await expect(page.getByRole("heading", { name: "Willkommen zurück" })).toBeVisible();
    await expect(page.getByText("admin@test.de")).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-dashboard.png", fullPage: true });
  });

  test("onboarding checklist is visible and shows first step as next", async ({ page }) => {
    await expect(page.getByText("Erste Schritte")).toBeVisible();
    // Progress — "0/3"
    await expect(page.getByText(/0\/3/)).toBeVisible();
    // First actionable step gets a CTA button
    await expect(page.getByRole("link", { name: /Verifizieren/ })).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/02-onboarding.png", fullPage: true });
  });

  test("quick-access tiles are all visible", async ({ page }) => {
    await expect(page.getByText("Artikelsuche")).toBeVisible();
    await expect(page.getByText("Ratsinformationssystem")).toBeVisible();
    await expect(page.getByText("Meine Themen")).toBeVisible();
    await expect(page.getByText("Telegram verbinden")).toBeVisible();
  });

  test("clicking Artikelsuche tile navigates to /nwz", async ({ page }) => {
    await page.getByRole("link", { name: "Artikelsuche" }).first().click();
    await page.waitForURL("/nwz");
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
