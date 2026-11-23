// Was der Fragen-Screen beim letzten Mal schon wusste — rein client-seitig
// (localStorage, kein Backend), nach dem Muster von lib/recent-searches.ts.
//
// Grund (Tims Befund 15.08.): Beim Tippen auf den Fragen-Tab standen erst
// Platzhalter und ein leerer Kopf, eine halbe Sekunde später erschienen die
// Beispielfragen und der Gespräche-Knopf — nichts sprang mehr (das war der
// Fix davor), aber alles „poppte auf". Beides hängt an Antworten, die schon
// beim letzten Besuch dieselben waren. Also: letzten Stand sofort zeichnen,
// im Hintergrund auffrischen, und das Ergebnis für das nächste Mal ablegen.

const KEY_QUESTIONS = "ratslotse:qa-fragen";
const KEY_OFFSET = "ratslotse:qa-fragen-weiter";
const KEY_GESPRAECHE = "ratslotse:qa-hat-gespraeche";
// Bis 22.11.2026 lagen hier die erzeugten Vorschläge aus der jüngsten Sitzung.
// Gelesen wird der Eintrag nicht mehr; beim ersten Speichern räumen wir ihn weg.
const KEY_ALT = "ratslotse:qa-beispiele";

/** Die kuratierten Beispielfragen, wie der Server sie zuletzt geliefert hat
 *  (`council/example_questions.py`). `null` heißt: auf diesem Gerät noch nie
 *  geladen. Nur dann sind Platzhalter richtig, sonst stehen die Fragen vom
 *  letzten Mal sofort, und der Abruf frischt sie fürs nächste Mal auf. */
export function readExampleQuestions(): string[] | null {
  try {
    const raw = localStorage.getItem(KEY_QUESTIONS);
    if (!raw) return null;
    const p = JSON.parse(raw) as unknown;
    if (!Array.isArray(p)) return null;
    const questions = p.filter((x): x is string => typeof x === "string" && x.trim() !== "");
    return questions.length > 0 ? questions : null;
  } catch {
    return null;
  }
}

export function storeExampleQuestions(questions: string[]): void {
  try {
    localStorage.setItem(KEY_QUESTIONS, JSON.stringify(questions));
    localStorage.removeItem(KEY_ALT);
  } catch {
    /* Storage voll/gesperrt — Feature ist optional */
  }
}

/** Wie viele Beispielfragen dieses Gerät schon gesehen hat. Der Zähler läuft
 *  einfach weiter; wo in der Liste das liegt, rechnet `exampleWindow` aus.
 *  So muss er die Länge der Liste nicht kennen, und eine neue Liste vom
 *  Server bringt ihn nicht durcheinander. */
export function readExampleOffset(): number {
  try {
    const n = Number(localStorage.getItem(KEY_OFFSET));
    return Number.isSafeInteger(n) && n >= 0 ? n : 0;
  } catch {
    return 0;
  }
}

/** Beim nächsten Besuch die nächsten `shown` Fragen (Tims Wunsch 22.11.2026:
 *  „bei jedem Aktualisieren rotieren“). Weiterrücken statt würfeln: Zufall
 *  zeigt dieselbe Frage oft zweimal hintereinander und manche wochenlang gar
 *  nicht. So kommt jede der zwanzig dran, bevor sich eine wiederholt. */
export function advanceExampleOffset(shown: number): void {
  try {
    const next = readExampleOffset() + Math.max(0, Math.floor(shown));
    // Nach einer Million Besuchen von vorn, statt irgendwann unsicher zu zählen.
    localStorage.setItem(KEY_OFFSET, String(next % 1_000_000));
  } catch {
    /* ohne Speicher steht eben jedes Mal derselbe Anfang da */
  }
}

/** `count` Fragen ab Position `offset`, über das Listenende hinweg weiter am
 *  Anfang. Nie mehr Fragen, als die Liste hat, und keine doppelt. */
export function exampleWindow(questions: readonly string[], offset: number, count: number): string[] {
  const n = questions.length;
  if (n === 0 || count <= 0) return [];
  const start = ((Math.floor(offset) % n) + n) % n;
  return Array.from({ length: Math.min(count, n) }, (_, i) => questions[(start + i) % n]);
}

/** Hatte das Konto beim letzten Besuch gespeicherte Gespräche? Damit steht der
 *  Kopf-Knopf sofort statt erst nach dem Laden der Liste. Falsch liegt der
 *  Wert nur, wenn man zwischendurch alle Gespräche gelöscht hat — dann
 *  verschwindet der Knopf einmal beim nächsten Laden und der Wert stimmt
 *  wieder. */
export function leseHatGespraeche(): boolean {
  try {
    return localStorage.getItem(KEY_GESPRAECHE) === "1";
  } catch {
    return false;
  }
}

export function merkeHatGespraeche(hat: boolean): void {
  try {
    localStorage.setItem(KEY_GESPRAECHE, hat ? "1" : "0");
  } catch {
    /* egal */
  }
}
