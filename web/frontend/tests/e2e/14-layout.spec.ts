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
import { zustandsDatei } from "./konten";


/** Die Seiten, die ein gewöhnliches Konto erreicht. */
const SEITEN = [
  "/dashboard", "/council", "/council?tab=sessions", "/fragen",
  "/topics", "/abos", "/bookmarks", "/account", "/quiz",
];

/** Öffentliche Seiten — auch sie werden auf dem Handy gelesen. */
const OFFEN = ["/", "/login", "/register", "/hilfe", "/impressum", "/datenschutz",
  // Der Wahlabend ohne Feature-Schalter: nur der Hinweis, aber mit eigenem
  // Kopf — und der ist auf dem Handy die enge Stelle. Die Tafel mit Zahlen
  // prüft `15-wahlabend.spec.ts`, dort mit gemockter Antwort.
  "/wahlabend",
  // Dasselbe Muster fürs Tippspiel: ohne Schalter nur der Hinweis, mit
  // gemockten Antworten prüft `16-tippspiel.spec.ts` die Handy-Screens und
  // `17-tippspiel-live.spec.ts` den Beamer.
  "/tipp", "/tipp/live"];

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

  // Eigener Block, weil `test.use({ storageState })` je BLOCK gilt: Darüber
  // stehen die Seiten, die OHNE Konto aufgehen müssen. Das `viewport` von
  // oben erbt dieser Block mit.
  test.describe("angemeldet", () => {
    test.use({ storageState: zustandsDatei("nutzerin") });

    for (const pfad of SEITEN) {
      test(`${pfad} bleibt in der Breite (angemeldet)`, async ({ page }) => {
        await page.goto(pfad, { waitUntil: "networkidle" });
        const zuviel = await ueberbreite(page);
        expect(zuviel, `${pfad} ist ${zuviel}px zu breit. Schuldige:\n  `
          + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
      });
    }
  });
});

test.describe("Schmalstes übliches Gerät (320px)", () => {
  // Ein iPhone SE der ersten Generation misst 320px. Wer dort scrollt,
  // scrollt auch auf jedem größeren Gerät bei größerer Schrift.
  test.use({ viewport: { width: 320, height: 568 } });

  test("/login bleibt in der Breite", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });
    const zuviel = await ueberbreite(page);
    expect(zuviel, `/login ist ${zuviel}px zu breit. Schuldige:\n  `
      + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
  });

  test.describe("angemeldet", () => {
    test.use({ storageState: zustandsDatei("nutzerin") });

    test("/dashboard bleibt in der Breite", async ({ page }) => {
      await page.goto("/dashboard", { waitUntil: "networkidle" });
      const zuviel = await ueberbreite(page);
      expect(zuviel, `/dashboard ist ${zuviel}px zu breit. Schuldige:\n  `
        + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
    });
  });

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

/* ------------------------ Die Antwort von „Frag den Rat" ------------------------ */

// Die Antwort-Seite ist keine Adresse, die man aufrufen kann — sie entsteht
// erst mit einer Frage, und ihre breitesten Bausteine erscheinen nur mit
// Daten. Deshalb gestubbt: Antwortstrom wie in `07-qa-feedback.spec.ts`,
// dazu die Fraktions-Positionen, die der Baustein „Aus den Ratsdebatten"
// nachlädt. So genügt auch die leere CI-Datenbank.
//
// Der Anlass (02.10.2026, 375 px, „Wie ist der Stand beim Stadionneubau?"):
// Die Zeile „Bündnis 90/Die Grünen · dagegen · 12 Beiträge · Dazu fragen"
// brach nicht um. Der Name stand auf drei Zeilen, „Dazu fragen" ragte trotzdem
// 32 px über den Rand — und mit der Seite rutschten Eingabezeile und
// Anschlussfragen rechts aus dem Bild.
const FRAGE = "Wie ist der Stand beim Stadionneubau?";
const ANTWORT_STROM = [
  { type: "step", step: "answer" },
  {
    type: "sources", question: FRAGE, qtype: "status",
    sources: [{
      id: 8679, title: "Stadionneubau – Übernahme einer Ausfallbürgschaft",
      committee: "Rat", session_date: "2025-12-15", outcome: "accepted", kind: "decision",
    }],
    debates: [{
      speaker: null, party: "Bündnis 90/Die Grünen", kind: "debate", agenda_item: null,
      excerpt: "Die Fraktion hält die Bürgschaft für ein zu großes Risiko für den Haushalt.",
      committee: "Rat", date: "2025-12-15",
    }],
  },
  { type: "token", text: "Der Rat hat die Ausfallbürgschaft für den Stadionneubau übernommen. [8679]" },
  {
    type: "suggestions", questions: [
      "Wie hoch ist die Ausfallbürgschaft für den Stadionneubau insgesamt?",
      "Welche Fraktionen haben gegen den Stadionneubau gestimmt?",
    ],
  },
  { type: "done", cited: [8679] },
].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

/** Die Zeilen, an denen es eng wird: langer Name, Haltung, Zähler — und
 *  einmal alles zugleich („Haltung gewandelt" + „uneinheitlich"). */
const PARTEIEN = {
  parties: [
    {
      party: "Bündnis 90/Die Grünen", stance: "dagegen", unanimous: true, note: null,
      position: "Hält die Bürgschaft für ein zu großes Risiko für den städtischen Haushalt.",
      kernaussage: { text: "Das Risiko trägt am Ende die Stadt.", speaker: null, date: "2025-12-15" },
      contributions: 12,
      beitraege_liste: [{ speaker: null, date: "2025-12-15", art: null, committee: "Rat", text: "Das Risiko trägt am Ende die Stadt." }],
    },
    {
      party: "Ortslandvolkverband Oldenburg", stance: "gewandelt", unanimous: false,
      note: "einzelne Stimmen dagegen",
      position: "Erst skeptisch, inzwischen für den Bau am bisherigen Standort.",
      kernaussage: null, contributions: 7,
      beitraege_liste: [{ speaker: null, date: "2025-06-02", art: null, committee: "Sport", text: "Der Standort ist inzwischen gesetzt." }],
    },
    {
      party: "SPD", stance: "dafür", unanimous: true, note: null,
      position: "Sieht im Stadion eine Investition in den Sport der Stadt.",
      kernaussage: null, contributions: 3,
    },
  ],
  without_speeches: ["FDP"],
};

for (const breite of [375, 320]) {
  test.describe(`Antwort mit Parteien-Baustein (${breite}px)`, () => {
    test.use({ storageState: zustandsDatei("nutzerin"), viewport: { width: breite, height: 812 } });

    test("bleibt in der Breite", async ({ page }) => {
      // Abzeichen sind eine eigene Oberfläche und legen sich sonst über die
      // erste Antwort (s. `17-lesbarkeit.spec.ts`).
      await page.route("**/api/badges**", (route) => route.fulfill({
        json: { badges: [], newly_earned: [], earned_count: 0, total: 0 },
      }));
      await page.route("**/api/council/ask", (route) =>
        route.fulfill({ status: 200, contentType: "text/event-stream", body: ANTWORT_STROM }));
      await page.route("**/api/council/party-meinungen", (route) =>
        route.fulfill({ json: PARTEIEN }));

      await page.goto("/fragen");
      await page.getByPlaceholder(/Deine Frage/).fill(FRAGE);
      await page.keyboard.press("Enter");
      // Erst wenn die Fraktionszeilen stehen, ist die breiteste Stelle da —
      // vorher zeigt der Baustein nur das Lade-Gerüst.
      await expect(page.getByText("Bündnis 90/Die Grünen", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: /Dazu fragen/ }).first()).toBeVisible();

      const zuviel = await ueberbreite(page);
      expect(zuviel, `Die Antwort ist bei ${breite}px ${zuviel}px zu breit. Schuldige:\n  `
        + (await ueberstehende(page)).join("\n  ")).toBeLessThanOrEqual(1);
    });
  });
}
