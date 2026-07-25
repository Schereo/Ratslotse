// Getippte Arbeit über eine abgelaufene Sitzung retten (Design 29a, P8).
//
// Bei einem 401 zeigt lib/api.ts einen Toast und schickt zur Anmeldung. Wer
// zwei Minuten an einer KI-Frage oder einer Themenbeschreibung geschrieben hat,
// fand danach ein leeres Feld — die App kassierte genau den Moment, in dem
// jemand wirklich mitarbeiten wollte.
//
// Rein client-seitig wie lib/recent.ts: Entwurf und Rücksprungziel landen in
// sessionStorage (nicht localStorage — der Entwurf soll nicht ewig herumliegen
// und nicht in anderen Tabs auftauchen), werden nach der Anmeldung einmalig
// zurückgespielt und dabei gelöscht.

const KEY = "ratslotse:entwurf";
/** Nach dieser Zeit ist ein Entwurf kalter Kaffee und wird verworfen. */
const HALTBAR_MS = 30 * 60 * 1000;

export type Entwurf = {
  /** Wer den Text zurückholt — frei gewählte Kennung des Feldes. */
  feld: string;
  text: string;
  /** Wohin es nach der Anmeldung zurückgehen soll (Pfad inkl. Query). */
  zurueck: string;
  gespeichertAm: number;
};

/** Aktuell offene Entwürfe. Felder melden sich hier an, solange etwas im
 *  Eingabefeld steht; bei einem 401 wird der zuletzt gemeldete Stand gesichert. */
const offen = new Map<string, () => string>();

/** Ein Eingabefeld anmelden. Gibt die Abmeldung zurück (für useEffect). */
export function entwurfMelden(feld: string, lesen: () => string): () => void {
  offen.set(feld, lesen);
  return () => { offen.delete(feld); };
}

/** Bei 401 aufgerufen: den längsten offenen Entwurf sichern. Mehrere Felder
 *  gleichzeitig zu retten brächte nichts — zurück kommt man nur an eine Stelle. */
export function entwurfSichern(zurueck: string): void {
  let beste: { feld: string; text: string } | null = null;
  for (const [feld, lesen] of offen) {
    let text = "";
    try { text = lesen().trim(); } catch { /* Komponente schon weg */ }
    if (text.length > 2 && (!beste || text.length > beste.text.length)) beste = { feld, text };
  }
  if (!beste) return;
  try {
    const e: Entwurf = { ...beste, zurueck, gespeichertAm: Date.now() };
    sessionStorage.setItem(KEY, JSON.stringify(e));
  } catch {
    /* Speicher voll/gesperrt — dann ist der Text eben weg, wie vorher */
  }
}

/** Gesicherten Entwurf für dieses Feld holen und dabei löschen (einmalig). */
export function entwurfAbholen(feld: string): string | null {
  try {
    const roh = sessionStorage.getItem(KEY);
    if (!roh) return null;
    const e = JSON.parse(roh) as Entwurf;
    if (e.feld !== feld) return null;
    sessionStorage.removeItem(KEY);
    if (Date.now() - e.gespeichertAm > HALTBAR_MS) return null;
    return e.text || null;
  } catch {
    return null;
  }
}

/** Wohin nach der Anmeldung zurück? Löscht den Eintrag NICHT — das macht erst
 *  {@link entwurfAbholen}, wenn das Feld den Text wirklich übernommen hat. */
export function entwurfZiel(): string | null {
  try {
    const roh = sessionStorage.getItem(KEY);
    if (!roh) return null;
    const e = JSON.parse(roh) as Entwurf;
    if (Date.now() - e.gespeichertAm > HALTBAR_MS) {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return e.zurueck || null;
  } catch {
    return null;
  }
}
