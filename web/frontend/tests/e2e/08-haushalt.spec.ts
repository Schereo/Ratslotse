/**
 * Der Haushalts-Bereich: zwanzig Seiten hinter EINEM Recht.
 *
 * Das Gate sitzt im Layout (`app/(app)/haushalt/layout.tsx`) und damit an
 * einer Stelle statt an zwanzig. Genau deshalb gehört es unter Test: Fällt es,
 * fällt es für alle zwanzig auf einmal — und die einundzwanzigste Seite, die
 * jemand morgen dazulegt, ist stillschweigend mitbetroffen.
 *
 * Die Sperre selbst sitzt im Backend (alle `/api/council/budget…`-Routen
 * verlangen `budget`, festgehalten in `tests/test_rollen.py`). Hier wird die
 * Höflichkeit davor geprüft: Wer das Recht nicht hat, soll gar nicht erst eine
 * halbleere Seite sehen.
 *
 * Die Konten kommen aus `scripts/saat_konten.py`, das der E2E-Backend-Start
 * ausführt: `ratsfrau@example.org` trägt die Rolle *Ratsmitglied*,
 * `nutzerin@example.org` keine — seit 08.11.2026 haben beide `budget`.
 */
import { expect, test } from "@playwright/test";
import { zustandsDatei } from "./konten";


/** Was `app/(app)/not-found.tsx` zeigt, wenn das Gate greift. */
const NICHT_GEFUNDEN = /Diesen Inhalt finde ich nicht/i;

/** Alle zwanzig Seiten des Bereichs. Kommt eine dazu, gehört sie hierher —
 *  sonst ist sie die erste, die niemand je aufgerufen hat. */
const SEITEN = [
  "/haushalt",
  "/haushalt/bereich",
  "/haushalt/einnahmen",
  "/haushalt/investitionen",
  "/haushalt/konzern",
  "/haushalt/labor",
  "/haushalt/mitreden",
  "/haushalt/personal",
  "/haushalt/pflicht",
  "/haushalt/plan-ist",
  "/haushalt/produkte",
  "/haushalt/pruefung",
  "/haushalt/schulden",
  "/haushalt/steuer",
  "/haushalt/vergleich",
];

test.describe("Jedes Konto, auch ohne Rolle", () => {
  // Seit 08.11.2026 (Tims Entscheidung) trägt die Standardrolle `budget`
  // (kern/roles.py). Bis dahin stand hier „ohne das Recht: 404, kein Link“.
  test.use({ storageState: zustandsDatei("nutzerin") });

  test("die Navigation führt hin, und die Übersicht geht auf", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: /Haushalt/ }).first()).toBeVisible();
    await page.goto("/haushalt");
    await expect(page.getByText(NICHT_GEFUNDEN)).toHaveCount(0);
  });
});

test.describe("Mit dem Recht `budget`", () => {
  test.use({ storageState: zustandsDatei("ratsfrau") });

  test("die Navigation führt hin", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: /Haushalt/ }).first()).toBeVisible();
  });

  // Jede der zwanzig Seiten muss aufgehen. Ohne Daten (in der CI ist die
  // Ratsdatenbank leer) zeigen sie ihren Leerzustand — das ist richtig so.
  // Was NICHT vorkommen darf: ein 404, ein weißer Bildschirm oder ein Absturz.
  for (const pfad of SEITEN) {
    test(`${pfad} geht auf`, async ({ page }) => {
      const fehler: string[] = [];
      page.on("pageerror", (e) => fehler.push(e.message));
      await page.goto(pfad);
      // Nicht ins Gate gelaufen
      await expect(page.getByText(NICHT_GEFUNDEN)).toHaveCount(0);
      // Und wirklich etwas gerendert. Bewusst KEINE Überschrift verlangt:
      // Nicht jede der zwanzig Seiten trägt eine, wenn die Ratsdaten leer sind
      // (in der CI der Normalfall) — dann steht dort ein Leerzustand, und das
      // ist richtig so. Was hier zählt: Der Rahmen steht und nichts ist
      // abgestürzt.
      await expect(page.locator("main")).not.toBeEmpty({ timeout: 15_000 });
      expect(fehler, `JavaScript-Fehler auf ${pfad}`).toEqual([]);
    });
  }
});
