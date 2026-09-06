/**
 * Das eigene Konto: Anzeigename, Passwort, Erscheinungsbild, Abmelden — und
 * die Löschung, die NICHT versehentlich passieren darf.
 *
 * Der Bereich war bisher nur als Screenshot abgedeckt („rendert ohne Fehler").
 * Gerade hier zählt aber, was auf einen Klick hin geschieht: Ein Konto zu
 * löschen ist der einzige Vorgang der App, den niemand zurücknehmen kann.
 */
import { expect, test } from "@playwright/test";
import { einrichtungUeberspringen, expectToast } from "./helpers";

const PASSWORT = "password123";
const KONTO = "nutzerin@example.org";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill(KONTO);
  await page.locator("#password").fill(PASSWORT);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
  await page.goto("/account");
});

test.describe("Anzeigename", () => {
  test("lässt sich ändern und bleibt nach dem Neuladen stehen", async ({ page }) => {
    const feld = page.getByLabel("Anzeigename");
    await feld.fill("Testname");
    await page.getByRole("button", { name: "Speichern" }).first().click();
    await expectToast(page, /gespeichert/i);
    await page.reload();
    await expect(page.getByLabel("Anzeigename")).toHaveValue("Testname");
  });
});

test.describe("Passwort ändern", () => {
  test("weist zwei verschiedene Wiederholungen ab, ohne etwas zu ändern", async ({ page }) => {
    const abschnitt = page.locator("section, div").filter({ hasText: "Passwort ändern" }).last();
    await abschnitt.getByLabel("Aktuelles Passwort").fill(PASSWORT);
    await abschnitt.getByLabel("Neues Passwort", { exact: true }).fill("neuespasswort1");
    await abschnitt.getByLabel(/bestätigen/).fill("etwasanderes1");
    await abschnitt.getByRole("button", { name: /Passwort ändern|Speichern/ }).click();
    await expect(page.getByText(/stimmen nicht überein/i)).toBeVisible();
  });

  test("weist ein falsches aktuelles Passwort ab", async ({ page }) => {
    const abschnitt = page.locator("section, div").filter({ hasText: "Passwort ändern" }).last();
    await abschnitt.getByLabel("Aktuelles Passwort").fill("falschfalsch");
    await abschnitt.getByLabel("Neues Passwort", { exact: true }).fill("neuespasswort1");
    await abschnitt.getByLabel(/bestätigen/).fill("neuespasswort1");
    await abschnitt.getByRole("button", { name: /Passwort ändern|Speichern/ }).click();
    await expect(page.getByText(/konnte nicht geändert|falsch/i).first()).toBeVisible();
  });
});

test.describe("Erscheinungsbild", () => {
  test("im Web stehen genau zwei Einstellungen zur Wahl", async ({ page }) => {
    // „Automatisch" (dem System folgen) gibt es NUR in der App: Im Browser
    // wäre ein dritter Knopf ohne Wirkung, weil der Schalter dort binär ist.
    const wahl = page.getByRole("radiogroup", { name: "Erscheinungsbild" });
    await expect(wahl).toBeVisible();
    await expect(wahl.getByRole("radio")).toHaveCount(2);
    await expect(wahl.getByRole("radio", { name: /Hell/ })).toBeVisible();
    await expect(wahl.getByRole("radio", { name: /Dunkel/ })).toBeVisible();
  });

  test("Dunkel schaltet die Seite wirklich um und merkt es sich", async ({ page }) => {
    const wahl = page.getByRole("radiogroup", { name: "Erscheinungsbild" });
    await wahl.getByRole("radio", { name: /Dunkel/ }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(wahl.getByRole("radio", { name: /Dunkel/ })).toHaveAttribute("aria-checked", "true");
    // Die Wahl überlebt einen Seitenwechsel — sonst wäre sie nur ein Blinken.
    await page.goto("/dashboard");
    await expect(page.locator("html")).toHaveClass(/dark/);
  });
});

test.describe("Konto löschen", () => {
  // Der einzige Vorgang der App, den niemand zurücknehmen kann. Er steht
  // deshalb hinter ZWEI Hürden: dem Passwort und einer Rückfrage.

  test("der Knopf bleibt gesperrt, solange kein Passwort dasteht", async ({ page }) => {
    const knopf = page.getByRole("button", { name: "Konto löschen" });
    await expect(knopf).toBeDisabled();
    await page.locator("#delete-password").fill(PASSWORT);
    await expect(knopf).toBeEnabled();
  });

  test("fragt nach und löscht nicht auf den ersten Klick", async ({ page }) => {
    await page.locator("#delete-password").fill(PASSWORT);
    await page.getByRole("button", { name: "Konto löschen" }).click();
    await expect(page.getByText("Konto endgültig löschen?")).toBeVisible();
    await expect(page.getByText(/kann nicht rückgängig/i)).toBeVisible();
    // Noch ist NICHTS passiert — die Sitzung steht.
    const me = await page.request.get("/api/auth/me");
    expect(me.ok()).toBeTruthy();
  });

  test("Abbrechen lässt das Konto in Ruhe", async ({ page }) => {
    await page.locator("#delete-password").fill(PASSWORT);
    await page.getByRole("button", { name: "Konto löschen" }).click();
    await expect(page.getByText("Konto endgültig löschen?")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByText("Konto endgültig löschen?")).toHaveCount(0);
    const me = await page.request.get("/api/auth/me");
    expect(me.ok()).toBeTruthy();
  });
});

test.describe("Rechtliches ist von hier aus erreichbar", () => {
  test("auf dem Handy stehen die Pflicht-Links im Konto", async ({ page }) => {
    // Sie sind `desk:hidden`: Am Schreibtisch trägt sie der Seiten-Fuß, mobil
    // ist der aus. In der App ist der Konto-Tab die EINZIGE Stelle, an der
    // überhaupt ein Fuß steht (App-Store-Richtlinie 5.2) — fehlt er, ist das
    // ein Ablehnungsgrund im Review.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    for (const name of ["Impressum", "Datenschutz", "Barrierefreiheit", "Changelog"]) {
      await expect(page.getByRole("link", { name }).first()).toBeVisible();
    }
    await expect(page.getByText(/kein Angebot der Stadt Oldenburg/)).toBeVisible();
  });
});

test.describe("Abmelden", () => {
  test("beendet die Sitzung wirklich — nicht nur die Ansicht", async ({ page }) => {
    await page.getByRole("button", { name: "Abmelden" }).click();
    await page.waitForURL(/\/login/, { timeout: 15_000 });
    // Die eigentliche Prüfung: Das Cookie ist weg, nicht nur die Seite gewechselt.
    const me = await page.request.get("/api/auth/me");
    expect(me.status()).toBe(401);
    // Und die geschützte Seite ist wieder zu.
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 15_000 });
  });
});
