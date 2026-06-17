import { Page, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@test.de";
const ADMIN_PASSWORD = "password123";

/** Register + login the admin account (first user). Returns when on /dashboard or /link. */
export async function registerAdmin(page: Page) {
  await page.goto("/register");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
}

/** Login an already-existing admin account. */
export async function loginAdmin(page: Page) {
  // Try to register first (idempotent for the test suite),
  // then just login if already registered.
  await page.goto("/login");
  await page.locator("#email").fill(ADMIN_EMAIL);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
}

/** Wait for toast message to appear. */
export async function expectToast(page: Page, text: string | RegExp) {
  await expect(page.locator("[data-sonner-toast]")).toContainText(text);
}

export { ADMIN_EMAIL, ADMIN_PASSWORD };
