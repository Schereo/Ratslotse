/**
 * Die Schritte, die ein Antwort-Strom über sich meldet — und ihr Text.
 *
 * Beide Endpunkte schicken denselben SSE-Rahmen `{"type":"step","step":…}`:
 * `/council/ask` als `expand → search → answer` (die KI-Frage), `/council/explain`
 * als `context → answer` (Lottis Erklärung). Bis 22.09.2026 kannte nur die
 * Fragen-Seite diese Rahmen; Lottis Fenster warf sie weg und zeigte statt
 * dessen drei blasse Punkte — „man sieht fast nicht, dass da was lädt" (Tim).
 *
 * Die Zuordnung steht hier und nicht in den beiden Komponenten, damit ein
 * neuer Schritt im Backend an EINER Stelle einen Text bekommt. Zwei Fassungen
 * liefen unweigerlich auseinander.
 */

/** Die Schritte der KI-Frage (`POST /api/council/ask`). */
export type AskSchritt = "expand" | "search" | "answer";

/** Neutral formuliert — auf der Fragen-Seite antwortet „Ratslotse", nicht Lotti. */
export const ASK_SCHRITTE: Record<AskSchritt, string> = {
  expand: "Frage wird in Suchbegriffe übersetzt",
  search: "Beschlüsse werden durchsucht und sortiert",
  answer: "Antwort wird formuliert",
};

/** Die Schritte der Erklärung (`POST /api/council/explain`). */
export type ErklaerSchritt = "context" | "answer";

/**
 * In Lottis Stimme, weil sie im Chat-Fenster neben ihrem Kopf stehen: „Lotti
 * liest die Seite" sagt in vier Wörtern, was gerade passiert und warum es
 * einen Moment dauert — „Kontext wird gesammelt" sagt dasselbe für niemanden.
 */
export const ERKLAER_SCHRITTE: Record<ErklaerSchritt, string> = {
  context: "Lotti liest die Seite",
  answer: "Lotti schreibt",
};

/**
 * Der Text zu einem Schritt in Lottis Fenster — für beide Wege.
 *
 * `null`/unbekannt heißt: Der Strom läuft, hat aber noch nichts über sich
 * gesagt (der deterministische Weg meldet gar keinen Schritt und ist in
 * Millisekunden fertig). Dann steht da, was in jedem Fall wahr ist.
 */
export function lottiSchrittText(schritt: string | null | undefined,
                                 ratsfrage = false): string {
  if (ratsfrage && schritt && schritt in ASK_SCHRITTE) {
    return ASK_SCHRITTE[schritt as AskSchritt];
  }
  if (!ratsfrage && schritt && schritt in ERKLAER_SCHRITTE) {
    return ERKLAER_SCHRITTE[schritt as ErklaerSchritt];
  }
  return "Lotti überlegt";
}
