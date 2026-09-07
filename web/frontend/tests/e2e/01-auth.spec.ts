/**
 * Auth flow: register → login → me endpoint → logout.
 */
import { test, expect } from "@playwright/test";
import { loginAdmin, ADMIN_EMAIL, ADMIN_PASSWORD } from "./helpers";

test.describe("Auth", () => {
  // EIGENE, JEDES MAL NEUE ADRESSE — nicht ADMIN_EMAIL. Seit 09/2026 legt
  // `auth.setup.ts` die Identitäten der Suite vor dem ersten Test an, und
  // `admin@test.de` gehört dazu. Auf eine vorhandene Adresse antwortet die
  // Registrierung mit 409; die Seite bliebe stehen, und der Test scheiterte
  // als Zeitüberschreitung beim Warten auf die Weiterleitung — mit einer
  // Meldung, die nichts über die Ursache sagt.
  //
  // Der Test wird dadurch nicht schwächer: Geprüft ist, dass das Formular ein
  // NEUES Konto anlegt und danach weiterleitet. Dass diese Adresse kein Admin
  // wird, spielt hier keine Rolle — die Admin-Vergabe hängt an
  // `WEB_ADMIN_EMAIL` und wird an anderer Stelle geprüft.
  test("register creates an account and lands on link/dashboard", async ({ page }) => {
    const neu = `neu-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.org`;
    await page.goto("/register");
    await expect(page.getByText("Ratslotse")).toBeVisible();

    await page.locator("#email").fill(neu);
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
