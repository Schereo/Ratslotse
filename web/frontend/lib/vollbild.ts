/**
 * Läuft gerade ein Ablauf, der den ganzen Schirm für sich hat?
 *
 * Drei gibt es davon: den Einrichtungs-Assistenten (`onboarding-flow.tsx`,
 * `fixed inset-0`), Lottis Einladung zur Tour (`tour-einladung.tsx`, Dialog mit
 * Abdunkelung) und die geführte Tour selbst (`tour.tsx`, `fixed inset-0`).
 * Solange einer davon steht, hat nichts Schwebendes daneben etwas zu suchen.
 *
 * **Warum ein Ereignis und kein React-Kontext.** Die Assistentin hängt in der
 * App-Hülle (`app/(app)/layout.tsx`), die drei Abläufe hängen daneben — ein
 * Kontext müsste also über die Hülle gelegt und durch jede Seite gereicht
 * werden, nur damit zwei Geschwister voneinander wissen. Dasselbe Muster
 * benutzt das Öffnen von außen schon (`ratslotse:lotti-oeffnen`) und das
 * Küken, das Lottis Fenster ausweicht (`ratslotse:lotti-offen`).
 *
 * **Warum ein Satz von Marken und kein Wahrheitswert.** Assistent und
 * Einladung überlappen sich um einen Wimpernschlag (`VERZOEGERUNG_MS`), und
 * das Abmelden des einen darf den anderen nicht mit abräumen. Gezählt wird
 * deshalb, wer gerade steht — erst der leere Satz heißt „wieder frei".
 *
 * **Was es NICHT ist:** kein Riegel gegen Lotti. Nach dem Ablauf ist alles wie
 * vorher; der Knopf kommt zurück, der Verlauf im `sessionStorage` überlebt.
 */

import { useEffect, useState } from "react";

export const VOLLBILD_EVENT = "ratslotse:vollbild";

/** Wer gerade eine Vollfläche hält. Modul-Zustand statt Kontext (s. o.) —
 *  und er muss außerhalb von React lesbar sein, weil Hörer auch nach dem
 *  Ereignis noch aufbauen können. */
const laufend = new Set<string>();

export function vollbildAktiv(): boolean {
  return laufend.size > 0;
}

/** Ein Ablauf meldet sich an bzw. ab. `name` ist frei wählbar, muss aber je
 *  Ablauf derselbe sein — sonst räumt das Abmelden nichts weg. */
export function meldeVollbild(name: string, aktiv: boolean): void {
  const vorher = laufend.size > 0;
  if (aktiv) laufend.add(name);
  else laufend.delete(name);
  const jetzt = laufend.size > 0;
  if (vorher === jetzt) return;
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(VOLLBILD_EVENT, { detail: { aktiv: jetzt } }));
}

/** Meldet einen Ablauf an, solange `aktiv` gilt, und beim Aushängen wieder ab.
 *  Das Aushängen ist der wichtigere Teil: Die Tour endet, indem ihre
 *  Komponente `null` liefert — ohne das Abmelden bliebe der Knopf für immer
 *  weg. */
export function useVollbildMelden(name: string, aktiv: boolean): void {
  useEffect(() => {
    meldeVollbild(name, aktiv);
    return () => meldeVollbild(name, false);
  }, [name, aktiv]);
}

/** Der laufende Zustand, für alles, was daneben stehen würde. */
export function useVollbild(): boolean {
  const [aktiv, setAktiv] = useState(false);
  useEffect(() => {
    // Beim Aufbauen einmal nachsehen: Wer nach dem Ereignis mountet (ein
    // Seitenwechsel während der Tour), hätte es sonst verpasst.
    setAktiv(vollbildAktiv());
    const auf = () => setAktiv(vollbildAktiv());
    window.addEventListener(VOLLBILD_EVENT, auf);
    return () => window.removeEventListener(VOLLBILD_EVENT, auf);
  }, []);
  return aktiv;
}

/** Nur für Tests: den Satz zurücksetzen, ohne ein Ereignis zu senden. */
export function _vollbildZuruecksetzen(): void {
  laufend.clear();
}
