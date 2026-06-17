/**
 * Auth flow: register → login → me endpoint → logout.
 */
import { test, expect } from "@playwright/test";
import { registerAdmin, loginAdmin, ADMIN_EMAIL, ADMIN_PASSWORD } from "./helpers";

test.describe("Auth", () => {
  test("register creates admin and lands on link/dashboard", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByText("Stadtpuls")).toBeVisible();

    await page.locator("#email").fill(ADMIN_EMAIL);
    await page.locator("#password").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });

    await page.screenshot({ path: "test-results/screenshots/01-after-register.png", fullPage: true });
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(ADMIN_EMAIL);
    await page.locator("#password").fill("wrongpassword");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByText(/E-Mail oder Passwort|fehlgeschlagen/i)).toBeVisible();
    await page.screenshot({ path: "test-results/screenshots/01-login-error.png", fullPage: true });
  });

  test("login with correct credentials lands on dashboard", async ({ page }) => {
    await loginAdmin(page);
    await expect(page).toHaveURL(/\/(link|dashboard)/);
    await page.screenshot({ path: "test-results/screenshots/01-after-login.png", fullPage: true });
  });

  test("password toggle reveals password text", async ({ page }) => {
    await page.goto("/login");
    const pwInput = page.locator("#password");
    await pwInput.fill("mysecret");
    await expect(pwInput).toHaveAttribute("type", "password");
    // Click the show/hide button
    await page.locator('button[aria-label*="anzeigen"]').first().click();
    await expect(page.locator("#password")).toHaveAttribute("type", "text");
    await expect(page.locator("#password")).toHaveValue("mysecret");
    await page.screenshot({ path: "test-results/screenshots/01-password-visible.png", fullPage: true });
  });

  test("logout clears session and redirects to login", async ({ page }) => {
    await loginAdmin(page);
    await page.getByRole("button", { name: "Abmelden" }).click();
    await page.waitForURL("/login");
    await page.screenshot({ path: "test-results/screenshots/01-after-logout.png", fullPage: true });
  });
});
