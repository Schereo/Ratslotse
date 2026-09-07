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
import { zustandsDatei } from "./konten";

test.describe("Quiz", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

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
  // Je Identität ein eigener Block: `test.use` gilt für einen ganzen Block,
  // nicht für einen einzelnen Test. Vorher meldete sich jeder Test hier selbst
  // an — genau die Runde, die `konten.ts` einspart.

  test.describe("ein gewöhnliches Konto", () => {
    test.use({ storageState: zustandsDatei("nutzerin") });

    test("kommt nicht hinein", async ({ page }) => {
      await page.goto("/admin");
      // Kein Admin-Inhalt. Was genau kommt (404 oder Weiterleitung), ist der
      // Oberfläche überlassen — NICHT überlassen ist, dass Verwaltungsdaten
      // sichtbar werden.
      await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
      await expect(page.getByText("Web-Nutzer*innen")).toHaveCount(0);
    });

    test("sieht den Admin-Zugang auch nicht in der Navigation", async ({ page }) => {
      await page.goto("/dashboard");
      await expect(page.getByRole("link", { name: /^Admin$/ })).toHaveCount(0);
    });
  });

  test.describe("ein Ratsmitglied ohne Adminrecht", () => {
    // Wichtig, weil `budget` und `admin` zwei verschiedene Rechte sind: Wer
    // den Haushalt sehen darf, darf noch lange keine Konten verwalten.
    test.use({ storageState: zustandsDatei("ratsfrau") });

    test("kommt ebenfalls nicht hinein", async ({ page }) => {
      await page.goto("/admin");
      await expect(page.getByRole("heading", { name: "Admin" })).toHaveCount(0);
    });
  });

  test.describe("das Adminkonto", () => {
    test.use({ storageState: zustandsDatei("chef") });

    test("kommt hinein", async ({ page }) => {
      const fehler: string[] = [];
      page.on("pageerror", (e) => fehler.push(e.message));
      await page.goto("/admin");
      await expect(page.getByRole("heading", { name: "Admin" }).first()).toBeVisible({ timeout: 15_000 });
      expect(fehler).toEqual([]);
    });
  });
});
