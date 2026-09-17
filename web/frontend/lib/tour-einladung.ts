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

import { api } from "./api";

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

/** Die drei Stationen, die gezählt werden. */
export type TourStand = "eingeladen" | "gestartet" | "beendet";

/**
 * Eine Station am Konto zählen — fire and forget, wirft nie.
 *
 * **Warum das nötig ist.** Die Einladung lebte bis 09/2026 vollständig im
 * `localStorage`: Ob sie überhaupt jemand zu sehen bekommt und ob jemand ja
 * sagt, war nirgends zu beantworten — auch nicht in der Auswertung vom
 * 17.09.2026, in der sechs neue Konten den Assistenten zu Ende gemacht haben
 * und trotzdem niemand eine Frage gestellt hat. Die Einladung ist der eine
 * Moment, in dem die KI-Frage erklärt wird; ob er trägt, muss messbar sein.
 *
 * **Was NICHT mitgeht:** nichts außer der Station. Kein Zeitpunkt, kein Pfad,
 * keine Dauer — der Server setzt den Tag selbst und zählt je Konto und Tag
 * hoch, wie bei jedem anderen Funktions-Zähler auch.
 */
export function meldeTour(stand: TourStand): void {
  try {
    void api.post("/onboarding/tour", { stand }).catch(() => {
      /* Ein Zähler darf nichts kosten — auch keine Fehlermeldung. */
    });
  } catch {
    /* dito */
  }
}
