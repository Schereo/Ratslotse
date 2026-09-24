// Wie breit die App-Hülle eine Seite werden lässt.
//
// Die Hülle deckelt den Inhalt bei 1280 px, ab `weit` (1680 px) bei 1600 px.
// Auf 1440p und 21:9 blieb dadurch fast die Hälfte des Schirms leer (Tims
// Befund 24.09.2026, gemessen in docs/plan-breite-schirme.md §1). Der Deckel
// steigt aber NICHT für alle: Eine Seite, die nur eine Spalte kennt, würde
// einfach breiter — Suchtreffer und Tagesordnungen mit Zeilen über 2.000 px.
// Deshalb meldet sich jede Seite hier an, sobald sie mit dem Platz etwas
// anzufangen weiß.
//
// Als Liste hier und nicht als Kontext aus der Seite heraus: Das Layout
// rendert zuerst, eine Seite, die ihre Breite erst selbst meldet, spränge
// beim Laden von schmal auf breit.

export type HuellenBreite = "voll" | "ultra" | "normal";

/** Randlos: kein Deckel, kein Seitenpolster — die Seite füllt alles neben
 *  der Seitenleiste. Nur für Bühnen, deren Inhalt selbst Fläche ist (Karten). */
export const VOLLBREIT: readonly string[] = [
  "/karte",
];

/** Ab `ultra` (2200 px) bis 2200 px breit statt 1600 px. Nur Seiten, die
 *  den Platz in zusätzliche Spalten stecken, nicht in längere Zeilen. */
export const ULTRA_BREIT: readonly string[] = [
  "/dashboard",
  "/council/decision",
];

function ohneSchraegstrich(pfad: string): string {
  // Der statische Export hängt einen Schrägstrich an (s. lib/public-routes.ts).
  return pfad.length > 1 && pfad.endsWith("/") ? pfad.slice(0, -1) : pfad;
}

export function breiteFuer(pfad: string | null | undefined): HuellenBreite {
  if (!pfad) return "normal";
  const p = ohneSchraegstrich(pfad);
  if (VOLLBREIT.includes(p)) return "voll";
  if (ULTRA_BREIT.includes(p)) return "ultra";
  return "normal";
}

/** Die Klassen der Inhalts-Hülle in app/(app)/layout.tsx.
 *
 *  `--rl-luft` ist das Seiten-Polster oben und unten; viewport-hohe Seiten
 *  ziehen es von ihrer Höhe ab (s. fragen/view.tsx). Randlos ist es 0. */
export function huellenKlasse(breite: HuellenBreite): string {
  if (breite === "voll") return "w-full flex-1 [--rl-luft:0px]";
  const basis = "mx-auto w-full max-w-7xl flex-1 px-4 py-[var(--rl-luft)] [--rl-luft:1.5rem] sm:px-6 sm:[--rl-luft:2rem] lg:px-8 weit:max-w-[1600px]";
  return breite === "ultra" ? `${basis} ultra:max-w-[2200px]` : basis;
}

/** Das Polster der normalen Hülle, zum Nachreichen auf randlosen Seiten —
 *  für das, was dort KEINE Bühne ist: Ladeplatzhalter, Fehlerzustände. */
export const SEITEN_POLSTER = "px-4 py-6 sm:px-6 sm:py-8 lg:px-8";

/** Die Schwellen von `ultra` und `weit` aus tailwind.config.ts, für JavaScript. Nur dort
 *  nehmen, wo CSS allein nicht reicht — wenn eine Seite ab `ultra` Bausteine
 *  UMHÄNGT und sie dabei nicht doppelt einhängen darf (jede Instanz lädt). */
export const ULTRA_MEDIA = "(min-width: 2200px)";
/** Dasselbe für `weit`. */
export const WEIT_MEDIA = "(min-width: 1680px)";
