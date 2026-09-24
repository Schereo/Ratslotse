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
export type ErklaerSchritt = "context" | "answer" | "archiv";

/**
 * Der Schritt, der auf BEIDEN Wegen gilt: Lotti geht ins Archiv.
 *
 * Er kommt aus `/explain` (die Frage gehört deterministisch ins Archiv, der
 * Strom endet sofort mit `mode: "handoff"`) und bleibt stehen, während die
 * Ratsfrage anläuft — bis sie ihren ersten eigenen Schritt meldet. Er sagt
 * damit genau das, was die Person wissen will, wenn plötzlich etwas anderes
 * passiert als „Lotti erklärt die Seite": **warum**.
 */
export const ARCHIV_SCHRITT = "archiv";

/**
 * In Lottis Stimme, weil sie im Chat-Fenster neben ihrem Kopf stehen: „Lotti
 * liest die Seite" sagt in vier Wörtern, was gerade passiert und warum es
 * einen Moment dauert — „Kontext wird gesammelt" sagt dasselbe für niemanden.
 */
export const ERKLAER_SCHRITTE: Record<ErklaerSchritt, string> = {
  context: "Lotti liest die Seite",
  answer: "Lotti schreibt",
  archiv: "Das steht nicht auf der Seite — ich sehe im Ratsarchiv nach",
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
  // **Zuerst und auf beiden Wegen.** Der Archiv-Schritt kommt aus `/explain`
  // und bleibt stehen, während die Ratsfrage anläuft — dort gilt sonst die
  // Tabelle der KI-Frage, und die kennt ihn nicht.
  if (schritt === ARCHIV_SCHRITT) return ERKLAER_SCHRITTE.archiv;
  if (ratsfrage && schritt && schritt in ASK_SCHRITTE) {
    return ASK_SCHRITTE[schritt as AskSchritt];
  }
  if (!ratsfrage && schritt && schritt in ERKLAER_SCHRITTE) {
    return ERKLAER_SCHRITTE[schritt as ErklaerSchritt];
  }
  return "Lotti überlegt";
}

/** Lottis Selbstprüfung — die Stände aus den SSE-Rahmen `check` und
 *  `revision` (`POST /council/explain`, Schalter `lotti-selbstpruefung`). */
export type PruefStand = "running" | "good" | "poor" | "skipped";
export type NeufassungStand = "running" | "replaced" | "kept";

/** Was unter der Antwort steht, solange die Prüfung läuft — sonst `null`.
 *
 *  **Zwei Sätze, nicht mehr** (Tims Idee vom 24.09.2026: „bewerte die
 *  Antwort … ich verfasse die Antwort neu“). Ein gutes Urteil braucht keinen
 *  Satz: Der Hinweis verschwindet, die Antwort bleibt, wie sie war. Ein
 *  ausgefallener Prüfer (`skipped`) auch nicht — für die Person ist das
 *  derselbe Zustand. */
export function pruefHinweis(pruefung: PruefStand | null | undefined,
                             neufassung: NeufassungStand | null | undefined): string | null {
  if (neufassung === "running" || (pruefung === "poor" && !neufassung)) {
    return "Ich formuliere das genauer";
  }
  if (!neufassung && pruefung === "running") return "Lotti prüft ihre Antwort";
  return null;
}
