/** Der gemerkte Stand von Lottis Tour-Einladung.
 *
 *  Steht bewusst hier und nicht in der Komponente: Der Einrichtungs-Assistent
 *  setzt die Marke beim Abschluss selbst, die Komponente liest sie beim
 *  Aufbauen — beide brauchen den Schlüssel, und ein gegenseitiger Import
 *  zwischen ihnen wäre ein Kreis.
 *
 *  Warum eine Marke und nicht (nur) ein Ereignis: Das Ereignis erreicht nur,
 *  wer in genau dieser Sekunde gemountet ist. Die Einladung hängt in der
 *  App-Hülle, und die steht in mehreren Momenten nicht — beim Skelett, solange
 *  `/auth/me` läuft, und auf dem Sperrbildschirm vor der E-Mail-Bestätigung.
 *  Dazu kommt der Fall, der es auf Prod erwischt hat: Ein Tab, der seit vor
 *  einem Deploy offen ist, fährt den Assistenten noch mit dem ALTEN Bündel
 *  weiter — dort gibt es die Einladung gar nicht, und die Gelegenheit war
 *  einmalig vorbei. Eine Marke im Speicher überlebt das alles.
 */

const KEY = "ratslotse:tour-einladung";

/** "offen" — die Einladung ist dran; "erledigt" — beantwortet, egal wie. */
export type EinladungsStand = "offen" | "erledigt";

export function einladungStand(): EinladungsStand | null {
  if (typeof window === "undefined") return null;
  try {
    const wert = localStorage.getItem(KEY);
    return wert === "offen" || wert === "erledigt" ? wert : null;
  } catch {
    return null;
  }
}

export function merkeEinladung(wert: EinladungsStand) {
  if (typeof window === "undefined") return;
  try { localStorage.setItem(KEY, wert); } catch { /* Speicher gesperrt — egal */ }
}
