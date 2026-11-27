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

/**
 * Ein Eintrag im Suchweg der KI-Frage (seit 11/2026): was gerade passiert und,
 * sobald es da ist, was dabei herauskam.
 *
 * Der Server baut die Texte (`council/search_trail.py`) und schickt sie im
 * gewohnten `step`-Rahmen mit: `text` öffnet einen Eintrag, `detail` ohne
 * `text` ist das Ergebnis des zuletzt geöffneten. Anlass war Potsdams
 * Ratsinformations-Chatbot, der beim Warten jeden Schritt samt Fund zeigt.
 */
export type SuchwegEintrag = { step: string; text: string; detail?: string };

/** Was ein `step`-Rahmen am Suchweg ändert. Rein, damit es testbar bleibt. */
export function suchwegWeiter(
  eintraege: SuchwegEintrag[],
  rahmen: Record<string, unknown>,
): SuchwegEintrag[] {
  const step = typeof rahmen.step === "string" ? rahmen.step : "";
  const text = typeof rahmen.text === "string" ? rahmen.text.trim() : "";
  const detail = typeof rahmen.detail === "string" ? rahmen.detail.trim() : "";
  if (text) return [...eintraege, { step, text, ...(detail ? { detail } : {}) }];
  if (detail) {
    if (!eintraege.length) return eintraege;
    const letzter = eintraege[eintraege.length - 1];
    return [...eintraege.slice(0, -1), { ...letzter, detail }];
  }
  // Ein Server vor dem Suchweg schickt nur die Phase: dann deren alter Text,
  // je Phase einmal.
  if (!step || eintraege[eintraege.length - 1]?.step === step) return eintraege;
  const alt = ASK_SCHRITTE[step as AskSchritt];
  return alt ? [...eintraege, { step, text: alt }] : eintraege;
}

/** Die Schritte der Erklärung (`POST /api/council/explain`). */
export type ErklaerSchritt = "context" | "answer" | "archiv" | "lookup";

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
  // Lotti schlägt nach (Schalter `lotti-werkzeuge`). Der Rahmen trägt meist
  // einen eigenen `text` („Lotti sieht die Reihe … an“) — der hier ist der
  // Ersatz, falls nicht.
  lookup: "Lotti schlägt in den Daten nach",
};

/**
 * Der Text zu einem Schritt in Lottis Fenster — für beide Wege.
 *
 * `null`/unbekannt heißt: Der Strom läuft, hat aber noch nichts über sich
 * gesagt (der deterministische Weg meldet gar keinen Schritt und ist in
 * Millisekunden fertig). Dann steht da, was in jedem Fall wahr ist.
 */
export function lottiSchrittText(schritt: string | null | undefined,
                                 ratsfrage = false,
                                 text?: string | null): string {
  // Beim Nachschlagen sagt der Server selbst, WAS Lotti gerade ansieht.
  if (schritt === "lookup" && text) return text;
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
