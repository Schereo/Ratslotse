/**
 * Die Navigation und die Wege durch die App.
 *
 * Zwei Eigenschaften, die keine einzelne Seite prüft: dass jeder Punkt der
 * Navigation irgendwo ankommt, und dass der aktive Punkt LEUCHTET. Der zweite
 * hing schon einmal am Schluss-Schrägstrich des App-Exports — der
 * Sitzungen-Tab leuchtete in der App nie, und im Browser fiel es niemandem
 * auf, weil es dort ging.
 */
import { expect, test } from "@playwright/test";
import { einrichtungUeberspringen } from "./helpers";

const PASSWORT = "password123";

async function anmelden(page: import("@playwright/test").Page, email = "nutzerin@example.org") {
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(PASSWORT);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
}

/** Was ein gewöhnliches Konto in der Navigation erreichen können muss. */
const ZIELE = [
  { label: "Heute", pfad: /\/dashboard/ },
  { label: "Fragen", pfad: /\/fragen/ },
  { label: "Suche", pfad: /\/council/ },
  { label: "Meine Themen", pfad: /\/topics/ },
  { label: "Abos", pfad: /\/abos/ },
  { label: "Merkliste", pfad: /\/bookmarks/ },
  { label: "Quiz", pfad: /\/quiz/ },
];

test.describe("Jeder Punkt der Navigation kommt an", () => {
  test.beforeEach(async ({ page }) => anmelden(page));

  for (const { label, pfad } of ZIELE) {
    test(`„${label}“ führt zu ${pfad}`, async ({ page }) => {
      await page.goto("/dashboard");
      await page.getByRole("link", { name: label, exact: true }).first().click();
      await expect(page).toHaveURL(pfad, { timeout: 15_000 });
      await expect(page.locator("main")).not.toBeEmpty();
    });
  }
});

test.describe("Der aktive Punkt leuchtet", () => {
  test.beforeEach(async ({ page }) => anmelden(page));

  test("auf dem Dashboard ist „Heute“ markiert", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Heute", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
  });

  test("auch mit Schluss-Schrägstrich — der Fall aus der App", async ({ page }) => {
    // `next.config.mjs` setzt für den App-Export `trailingSlash: true`. Ein
    // exakter Vergleich (`pathname === "/topics"`) ist damit in der App blind.
    await page.goto("/topics/");
    await expect(page.getByRole("link", { name: "Meine Themen", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
  });

  test("die Reiter der Ratsseite markieren sich einzeln", async ({ page }) => {
    await page.goto("/council?tab=sessions");
    await expect(page.getByRole("link", { name: "Sitzungen", exact: true }).first())
      .toHaveAttribute("aria-current", "page");
    // Und „Suche" ist es dann NICHT — beide zeigen auf /council.
    await expect(page.getByRole("link", { name: "Suche", exact: true }).first())
      .not.toHaveAttribute("aria-current", "page");
  });
});

test.describe("Deep-Links kommen an", () => {
  test.beforeEach(async ({ page }) => anmelden(page));

  test("ein Reiter aus der Adresse wird übernommen", async ({ page }) => {
    for (const tab of ["sessions", "decisions"]) {
      await page.goto(`/council?tab=${tab}`);
      await expect(page).toHaveURL(new RegExp(`tab=${tab}`));
      await expect(page.locator("main")).not.toBeEmpty();
    }
  });

  test("eine unbekannte Kennung endet im App-eigenen 404, nicht im Nichts", async ({ page }) => {
    await page.goto("/council/decision?id=99999999");
    // Die App-eigene 404 erbt die Hülle: Navigation und Suche bleiben da.
    await expect(page.getByText(/finde ich nicht/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: "Heute", exact: true }).first()).toBeVisible();
  });
});

test.describe("Mobil", () => {
  test("die untere Leiste trägt die Hauptpunkte", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await anmelden(page);
    await page.goto("/dashboard");
    for (const label of ["Start", "Fragen"]) {
      await expect(page.getByRole("link", { name: label, exact: true }).first()).toBeVisible();
    }
  });
});
