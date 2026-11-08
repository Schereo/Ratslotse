/**
 * Läuft gerade die Lotti-Tour (in diesem Tab)?
 *
 * Geteilt zwischen der Tour und allem, was während der Führung anders zählen
 * soll. Erster Fall: Abzeichen. Wer von der Tour auf die Analyse geführt wird,
 * hat sie nicht selbst erkundet (Tim 08.11.2026). Der Schlüssel ist derselbe,
 * unter dem die Tour ihren Schritt über ein Neuladen rettet — es gibt also
 * genau eine Wahrheit darüber, ob sie läuft.
 */
export const TOUR_STEP_KEY = "ratslotse:tour-schritt";

export function tourRunning(): boolean {
  try { return sessionStorage.getItem(TOUR_STEP_KEY) !== null; } catch { return false; }
}
