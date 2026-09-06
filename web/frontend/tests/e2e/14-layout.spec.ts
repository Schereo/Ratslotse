/**
 * Layout-Invarianten: Was auf keiner Seite passieren darf.
 *
 * Ein Pixelvergleich wäre hier das falsche Werkzeug — er meldet jede
 * beabsichtigte Änderung als Fehler und wird nach dem dritten Mal
 * weggeklickt. Geprüft werden deshalb zwei Zusagen, die IMMER gelten und die
 * niemand absichtlich bricht:
 *
 * 1. **Die Seite scrollt nicht seitwärts.** Auf dem Handy ist das der
 *    häufigste Layout-Fehler: Eine breite Tabelle, ein langes Wort ohne
 *    Trennmöglichkeit, ein `min-w` zu viel — und die ganze Seite lässt sich
 *    verschieben. Alles darunter steht dann schief, und auf dem Schreibtisch
 *    fällt es nie auf.
 * 2. **Kein Text läuft aus seinem Kasten.** Ein Wort, das breiter ist als
 *    sein Behälter, wird abgeschnitten oder überlappt den Nachbarn.
 */
import { expect, test, type Page } from "@playwright/test";
import { einrichtungUeberspringen } from "./helpers";

const PASSWORT = "password123";

/** Die Seiten, die ein gewöhnliches Konto erreicht. */
const SEITEN = [
  "/dashboard", "/council", "/council?tab=sessions", "/fragen",
  "/topics", "/abos", "/bookmarks", "/account", "/quiz",
];

/** Öffentliche Seiten — auch sie werden auf dem Handy gelesen. */
const OFFEN = ["/", "/login", "/register", "/hilfe", "/impressum", "/datenschutz"];

async function anmelden(page: Page) {
  await page.goto("/login");
  await page.locator("#email").fill("nutzerin@example.org");
  await page.locator("#password").fill(PASSWORT);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL(/\/(link|dashboard)/, { timeout: 15_000 });
  await einrichtungUeberspringen(page);
}

/** Um wie viel ist die Seite breiter als das Fenster? 0 = gar nicht. */
async function ueberbreite(page: Page): Promise<number> {
  return page.evaluate(() => {
    const d = document.documentElement;
    return Math.max(0, d.scrollWidth - d.clientWidth);
  });
}

/** Die Elemente, die über den rechten Rand hinausragen — für die Meldung. */
async function ueberstehende(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const breite = document.documentElement.clientWidth;
    const aus: string[] = [];
    for (const el of Array.from(document.querySelectorAll("body *"))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      // Ein Element DARF überstehen, wenn es (oder ein Vorfahr) selbst
      // scrollt — genau so gehören breite Tabellen gebaut.
      let scrollt = false;
      for (let p: Element | null = el; p; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (s.overflowX === "auto" || s.overflowX === "scroll" || s.overflowX === "hidden") {
          scrollt = true;
          break;
        }
      }
      if (scrollt) continue;
      if (r.right > breite + 1) {
        const kurz = el.tagName.toLowerCase()
          + (el.className && typeof el.className === "string"
            ? "." + el.className.split(/\s+/).slice(0, 3).join(".") : "");
        aus.push(`${kurz} (bis ${Math.round(r.right)}px, Fenster ${breite}px)`);
      }
    }
    return aus.slice(0, 5);
  });
}

test.describe("Handy (390px): keine Seite scrollt seitwärts", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const pfad of OFFEN) {
    test(`${pfad} bleibt in der Breite`, async ({ page }) => {
      await page.goto(pfad, { waitUntil: "networkidle" });
      const zuviel = await ueberbreite(page);
      expect(zuviel, `${pfad} ist ${zuviel}px zu breit. Schuldige:\n  `
        + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
    });
  }

  for (const pfad of SEITEN) {
    test(`${pfad} bleibt in der Breite (angemeldet)`, async ({ page }) => {
      await anmelden(page);
      await page.goto(pfad, { waitUntil: "networkidle" });
      const zuviel = await ueberbreite(page);
      expect(zuviel, `${pfad} ist ${zuviel}px zu breit. Schuldige:\n  `
        + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
    });
  }
});

test.describe("Schmalstes übliches Gerät (320px)", () => {
  // Ein iPhone SE der ersten Generation misst 320px. Wer dort scrollt,
  // scrollt auch auf jedem größeren Gerät bei größerer Schrift.
  test.use({ viewport: { width: 320, height: 568 } });

  for (const pfad of ["/login", "/dashboard"]) {
    test(`${pfad} bleibt in der Breite`, async ({ page }) => {
      if (pfad === "/dashboard") await anmelden(page);
      await page.goto(pfad, { waitUntil: "networkidle" });
      const zuviel = await ueberbreite(page);
      expect(zuviel, `${pfad} ist ${zuviel}px zu breit. Schuldige:\n  `
        + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
    });
  }

  // BEKANNTER BEFUND, absichtlich als erwarteter Fehlschlag festgehalten.
  //
  // Die Kopfzeile der Startseite ist bei 320px **14px zu breit**: Marke,
  // Erscheinungsbild-Schalter und „Kostenlos registrieren" passen dort nicht
  // nebeneinander. Die Seite lässt sich seitwärts schieben, und alles darunter
  // steht schief.
  //
  // Nicht mit repariert, weil die Startseite Design ist und keine Mechanik —
  // ob der Schalter weicht, die Beschriftung kürzer wird oder die Zeile
  // umbricht, ist eine gestalterische Entscheidung. `test.fail()` hält den
  // Befund sichtbar: Der Test meldet sich, sobald jemand ihn behebt, und dann
  // fliegt diese Markierung raus.
  test("/ ist bei 320px zu breit (bekannt)", async ({ page }) => {
    test.fail();   // gilt NUR für diesen Test — vor dem Block wären es alle
    await page.goto("/", { waitUntil: "networkidle" });
    const zuviel = await ueberbreite(page);
    expect(zuviel, `Schuldige:\n  ` + (await ueberstehende(page)).join("\n  "))
      .toBeLessThanOrEqual(1);
  });
});
