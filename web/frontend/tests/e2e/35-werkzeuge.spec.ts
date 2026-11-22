/**
 * Die Werkzeuge: ein Bereich hinter dem Recht `council_tools`.
 *
 * Das Gate sitzt im Layout (`app/(app)/werkzeuge/layout.tsx`), die Sperre im
 * Backend (`tests/test_werkzeuge.py`). Hier die Höflichkeit davor: Ein Konto
 * ohne Recht sieht weder den Navigationspunkt noch die Seite; ein
 * Ratsmitglied kommt hin, und der Rechner steht — mit Daten oder mit seinem
 * Leerzustand (in der CI ist die Ratsdatenbank leer).
 *
 * Konten aus `scripts/saat_konten.py`: `ratsfrau@example.org` trägt die
 * Rolle *Ratsmitglied*, `nutzerin@example.org` keine.
 */
import { expect, test } from "@playwright/test";
import { zustandsDatei } from "./konten";

const NICHT_GEFUNDEN = /Diesen Inhalt finde ich nicht/i;

test.describe("Ohne das Recht", () => {
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("kein Navigationspunkt, und die Seite ist ein 404", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Werkzeuge" })).toHaveCount(0);
    await page.goto("/werkzeuge/mehrheiten");
    await expect(page.getByText(NICHT_GEFUNDEN)).toBeVisible();
  });
});

test.describe("Als Ratsmitglied", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test("die Navigation führt hin, und der Rechner geht auf", async ({ page }) => {
    const fehler: string[] = [];
    page.on("pageerror", (e) => fehler.push(e.message));
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Werkzeuge" }).first().click();
    await expect(page).toHaveURL(/\/werkzeuge$/);
    await page.getByRole("link", { name: /Mehrheitsrechner/ }).click();
    await expect(page.getByRole("heading", { name: "Mehrheitsrechner" })).toBeVisible();
    // Mit Daten der Sitzbogen, ohne der Leerzustand — beides ist richtig.
    await expect(
      page.getByRole("img", { name: /Mehrheit ab/ }).or(page.getByText(/noch nicht geladen/)),
    ).toBeVisible();
    expect(fehler).toEqual([]);
  });
});
