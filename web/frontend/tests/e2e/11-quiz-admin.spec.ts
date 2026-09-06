/**
 * Quiz und Admin-Panel — die beiden Bereiche, die bisher gar nicht angefahren
 * wurden.
 *
 * Beim Admin-Panel zählt vor allem die Grenze: Es hängt am Recht `admin`, und
 * ein gewöhnliches Konto darf dort nicht landen. Beim Quiz zählt, dass es
 * seinen Leerzustand erklärt statt weiß zu bleiben — in der CI ist die
 * Ratsdatenbank leer, und genau so sieht auch eine frische Umgebung aus.
 */
import { expect, test } from "@playwright/test";
import { einrichtungUeberspringen } from "./helpers";

const PASSWORT = "password123";

async function anmelden(page: import("@playwright/test").Page, email: string) {
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(PASSWORT);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
}

test.describe("Quiz", () => {
  test.beforeEach(async ({ page }) => anmelden(page, "nutzerin@example.org"));

  test("die Seite geht auf und erklärt sich, auch ohne Fragen", async ({ page }) => {
    const fehler: string[] = [];
    page.on("pageerror", (e) => fehler.push(e.message));
    await page.goto("/quiz");
    // Entweder es gibt Fragen, oder die Seite sagt, dass gerade keine da sind.
    // Ein weißer Bildschirm ist in beiden Fällen falsch.
    await expect(page.locator("main")).not.toBeEmpty({ timeout: 15_000 });
    expect(fehler).toEqual([]);
  });

  test("die eigene Statistik ist erreichbar", async ({ page }) => {
    await page.goto("/quiz/stats");
    await expect(page.getByText(/Quiz-Statistik/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("bietet entweder ein Spiel an — oder sagt, dass gerade keins da ist", async ({ page }) => {
    // Der Bestand entscheidet, WAS dort steht: Mit Fragen die Kacheln
    // (darunter das Karten-Quiz), ohne Fragen der Vorbereitungs-Hinweis. Beide
    // sind richtig. Falsch wäre eine Seite, die weder das eine noch das andere
    // zeigt — und genau das fiel beim Lauf gegen eine LEERE Ratsdatenbank auf,
    // dem Zustand der CI.
    await page.goto("/quiz");
    const angebot = page.getByText(/Karten-Quiz|Neues Spiel|Meine Fragen üben/);
    const hinweis = page.getByText(/wird gerade vorbereitet/);
    await expect
      .poll(async () => (await angebot.count()) + (await hinweis.count()), { timeout: 15_000 })
      .toBeGreaterThan(0);
  });
});

test.describe("Admin-Panel — die Grenze", () => {
  test("ein gewöhnliches Konto kommt nicht hinein", async ({ page }) => {
    await anmelden(page, "nutzerin@example.org");
    await page.goto("/admin");
    // Kein Admin-Inhalt. Was genau kommt (404 oder Weiterleitung), ist der
    // Oberfläche überlassen — NICHT überlassen ist, dass Verwaltungsdaten
    // sichtbar werden.
    await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
    await expect(page.getByText("Web-Nutzer*innen")).toHaveCount(0);
  });

  test("ein Ratsmitglied ohne Adminrecht ebenfalls nicht", async ({ page }) => {
    // Wichtig, weil `budget` und `admin` zwei verschiedene Rechte sind: Wer
    // den Haushalt sehen darf, darf noch lange keine Konten verwalten.
    await anmelden(page, "ratsfrau@example.org");
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
  });

  test("das Adminkonto kommt hinein", async ({ page }) => {
    await anmelden(page, "chef@example.org");
    const fehler: string[] = [];
    page.on("pageerror", (e) => fehler.push(e.message));
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Admin" }).first()).toBeVisible({ timeout: 15_000 });
    expect(fehler).toEqual([]);
  });

  test("die Navigation zeigt den Admin-Zugang nur Admins", async ({ page }) => {
    await anmelden(page, "nutzerin@example.org");
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: /^Admin$/ })).toHaveCount(0);
  });
});
