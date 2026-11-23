/**
 * Gemeinsames Rüstzeug der Lotti-Browsertests: der gestubbte Erklär-Strom in
 * seinen Spielarten, der Schalter und die beiden Fundstellen Knopf und Fenster.
 *
 * Eigene Datei seit 11/2026, weil die Lotti-Tests auf drei Spec-Dateien
 * verteilt sind (`21-lotti-assistentin`, `-assistentin-2`, `-markieren`).
 * Vorher standen alle 59 in EINER Datei, und die war mit rund vier Minuten die
 * Untergrenze der ganzen CI: Eine Datei ist die kleinste Einheit, die sich auf
 * die Läufer verteilen lässt (`tests/shard-specs.mjs`).
 *
 * Kein Spec: Der Name endet nicht auf `.spec.ts`, Playwright sammelt hier
 * nichts ein.
 */
import { expect, type Page } from "@playwright/test";

export const ANTWORT = "Die Treppe zeigt, wie viel die Stadt in jedem Jahr zurückzahlt.";
export const GEPRUEFTE_ANTWORT = "Tilgung ist die Rückzahlung eines Kredits.";

export const STROM = (opts: { next?: string | null } = {}) => [
  `data: ${JSON.stringify({ type: "step", step: "context" })}\n\n`,
  `data: ${JSON.stringify({ type: "step", step: "answer" })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: ANTWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model",
    next: opts.next ?? null, glossary: ["Tilgung"], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Der Schalter kommt aus `/api/app-config`; ohne ihn gibt es keinen Knopf.
 *
 *  **Der try/catch ist nicht Vorsicht, sondern gemessen** (CI, 21.09.2026):
 *  Beendet ein `test.skip()` den Test, während dieser Handler noch auf die
 *  echte Antwort wartet, wirft Playwright „Response has been disposed" — und
 *  zwar in JEDEM danach laufenden Test derselben Datei, weil die Route
 *  weiterhin registriert ist. Ein Handler, der den Fehler schluckt und die
 *  Anfrage durchlässt, macht die ganze Datei gegen diesen Abbruch immun.
 */
export async function schalterAn(page: Page, an = true) {
  await page.route("**/api/app-config", async (route) => {
    try {
      const antwort = await route.fetch();
      const body = await antwort.json();
      const features: string[] = (body.features ?? []).filter((f: string) => f !== "lotti-assistentin");
      if (an) features.push("lotti-assistentin");
      await route.fulfill({ json: { ...body, features } });
    } catch {
      await route.fallback().catch(() => { /* der Test ist schon zu Ende */ });
    }
  });
}

/** Der Weg OHNE Modell: Glossar, Seiten-Wissen, „Lotti erklärt's einfach".
 *  Ein Token, ein `done` mit `mode: "deterministic"` — genau so schickt es
 *  `POST /council/explain`, wenn `deterministic_answer` getroffen hat. */
export const STROM_GEPRUEFT = [
  `data: ${JSON.stringify({ type: "token", text: GEPRUEFTE_ANTWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "deterministic", kind: "glossary",
    next: null, glossary: [], timings: { total_ms: 4 },
  })}\n\n`,
].join("");

/** Eine Modell-Antwort, in der ein Fachwort aus dem Glossar steht.
 *
 *  **„Tilgung" tut es nicht**, so naheliegend es auf der Schulden-Seite wäre:
 *  Das Glossar ist kuratiert (`kern/glossar.py`, 149 Begriffe) und kennt das
 *  Wort nicht. Ein Test auf ein Wort, das gar kein Begriff ist, prüfte die
 *  eigene Erwartung statt die Erkennung. */
export const ANTWORT_FACHWORT = "Die Stadt zahlt jedes Jahr zurück; eine Umschuldung ändert daran nichts.";

export const STROM_FACHWORT = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_FACHWORT })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null,
    glossary: ["Umschuldung"], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Eine Antwort, die auf eine andere Haushalts-Seite verweist (PR 21). Die
 *  Adresse steht NICHT im Text — sie reist im `done`-Rahmen als `next_page`,
 *  geprüft gegen `kern/knowledge.py` und die Rechte des Kontos. */
export const ANTWORT_SEITE = "Der Schuldenstand lag Ende 2024 bei rund 295 Millionen Euro.";

export const STROM_SEITE = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_SEITE })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null,
    next_page: { route: "/haushalt/schulden", title: "Schulden der Stadt" },
    glossary: [], timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Eine Antwort mit Haushaltszahlen (PR 28). Die Papiere reisen NICHT im
 *  Text, sondern im `done`-Rahmen als `evidence` — dieselbe Auswahl, die den
 *  Prompt gefüllt hat (`qa.geld_auswahl`).
 *
 *  Drei Belege, drei Fälle: einer, dessen Jahr noch fehlt (es kommt aus dem
 *  Baustein), einer, der es schon im Titel trägt, und einer ohne Adresse. */
export const ANTWORT_ZAHL = "Der Schuldenstand lag Ende 2024 bei rund 295 Millionen Euro.";
export const BELEGE = [
  { label: "Statistisches Jahrbuch, Tabelle 1108", year: 2024,
    url: "https://example.org/jahrbuch-1108.pdf" },
  { label: "Jahresabschluss 2023", year: 2023, url: "https://example.org/ja-2023.pdf" },
  { label: "Prüfbericht 2022", year: 2022, url: null },
];

export const STROM_BELEGE = [
  `data: ${JSON.stringify({ type: "token", text: ANTWORT_ZAHL })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "explain", kind: "model", next: null, next_page: null,
    glossary: [], evidence: BELEGE, timings: { total_ms: 900 },
  })}\n\n`,
].join("");

/** Der Strom, mit dem `/explain` eine Archivfrage beantwortet: **gar nicht.**
 *  Seit PR 23 entscheidet der Server am Wortlaut und schickt ohne einen
 *  einzigen Modellaufruf den Schritt plus `mode: "handoff"` — das Fenster
 *  stellt dann von selbst die Ratsfrage, als zweiten Schritt derselben Runde. */
export const STROM_HANDOFF = [
  `data: ${JSON.stringify({ type: "step", step: "archiv" })}\n\n`,
  `data: ${JSON.stringify({
    type: "done", mode: "handoff", kind: "archiv",
    next: "ratsfrage", next_page: null, glossary: [], timings: { total_ms: 3 },
  })}\n\n`,
].join("");

/** Die Ratsantwort aus dem Archiv — Quellen, Text, zitierte Nummern.
 *
 *  **Drei Fundstücke, eines zitiert**: genau die Lage, die Tim am
 *  22.09.2026 auf `/council/decision?id=2982` gesehen hat („1 zitiert · 41
 *  gefunden", darunter drei Zeilen, zwei davon zur Sache fremd). */
export const RATS_ANTWORT = "Der Rat hat 2026 zugestimmt.";
export const FUNDSTUECKE = [
  { id: 8525, title: "Stadionneubau Maastrichter Straße", committee: "Rat",
    session_date: "2026-06-01" },
  { id: 11, title: "Toleranz-Fonds 2026", committee: "Rat", session_date: "2026-03-01" },
  { id: 12, title: "Bebauungsplan Nr. 56", committee: "Rat", session_date: "2026-02-01" },
];
export const STROM_ARCHIV = [
  `data: ${JSON.stringify({ type: "sources", sources: FUNDSTUECKE })}\n\n`,
  `data: ${JSON.stringify({ type: "token", text: RATS_ANTWORT })}\n\n`,
  `data: ${JSON.stringify({ type: "done", cited: [8525] })}\n\n`,
].join("");

export async function stromStubben(page: Page, opts: { next?: string | null } = {}) {
  await page.route("**/api/council/explain", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: STROM(opts) })
      .catch(() => { /* der Test ist schon zu Ende */ }),
  );
}

export const knopf = (page: Page) => page.locator("[data-lotti-knopf]");
export const fenster = (page: Page) => page.locator("[data-lotti-fenster]");

/** Wartet, bis `/haushalt/schulden` entschieden hat: Überschrift (mit Daten)
 *  ODER der ehrliche Leerhinweis (leere CI-Datenbank).
 *
 *  Bis 10/2026 stand hier `waitForLoadState("networkidle")` — und das ist
 *  kein Zustand der Seite, sondern des Netzes: Ein Abfragen-Takt, ein
 *  nachgeladener Baustein oder ein Vorzustand aus dem Test davor hielt es
 *  offen, und der Test lief je nach Lage in den 30-s-Timeout. */
export async function schuldenGeladen(page: Page) {
  await expect(
    // `.first()`: Seit 11/2026 trägt auch der Leerhinweis die Überschrift
    // (unsichtbar, für Screenreader) — ohne Daten treffen dann beide zu.
    page.getByRole("heading", { name: "Schulden der Stadt" })
      .or(page.getByText(/Schuldenzeitreihe noch nicht eingelesen/)).first(),
  ).toBeVisible({ timeout: 20_000 });
}
