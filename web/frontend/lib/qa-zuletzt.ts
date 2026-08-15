// Was der Fragen-Screen beim letzten Mal schon wusste — rein client-seitig
// (localStorage, kein Backend), nach dem Muster von lib/recent-searches.ts.
//
// Grund (Tims Befund 15.08.): Beim Tippen auf den Fragen-Tab standen erst
// Platzhalter und ein leerer Kopf, eine halbe Sekunde später erschienen die
// Beispielfragen und der Gespräche-Knopf — nichts sprang mehr (das war der
// Fix davor), aber alles „poppte auf". Beides hängt an Antworten, die schon
// beim letzten Besuch dieselben waren. Also: letzten Stand sofort zeichnen,
// im Hintergrund auffrischen, und das Ergebnis für das nächste Mal ablegen.

const KEY_BEISPIELE = "ratslotse:qa-beispiele";
const KEY_GESPRAECHE = "ratslotse:qa-hat-gespraeche";

// Die frischen Vorschläge nennen ein Sitzungsdatum. Nach einer Woche ist das
// nicht falsch, aber auch kein Beleg mehr dafür, dass hier aktuelles Material
// liegt — dann lieber nur die Klassiker (die stehen sofort, ohne Nachladen).
const MAX_ALTER_MS = 7 * 24 * 60 * 60 * 1000;

/** Zuletzt gezeigte frische Vorschläge. `null` heißt: dieser Screen war hier
 *  noch nie: nur dann sind Platzhalter richtig. Ein leeres Array heißt
 *  „schon da gewesen, aber nichts Frisches" — dann stehen die Klassiker
 *  sofort. */
export function leseQaBeispiele(): { frisch: string[] } | null {
  try {
    const raw = localStorage.getItem(KEY_BEISPIELE);
    if (!raw) return null;
    const p = JSON.parse(raw) as { frisch?: unknown; ts?: unknown };
    const frisch = Array.isArray(p.frisch) ? p.frisch.filter((x): x is string => typeof x === "string") : [];
    const alt = typeof p.ts === "number" && Date.now() - p.ts > MAX_ALTER_MS;
    return { frisch: alt ? [] : frisch };
  } catch {
    return null;
  }
}

export function merkeQaBeispiele(frisch: string[]): void {
  try {
    localStorage.setItem(KEY_BEISPIELE, JSON.stringify({ frisch, ts: Date.now() }));
  } catch {
    /* Storage voll/gesperrt — Feature ist optional */
  }
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
