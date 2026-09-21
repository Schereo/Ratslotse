/**
 * Wie viel Platz die Bildschirmtastatur unten wegnimmt.
 *
 * **Warum das überhaupt nötig ist.** Ein Element mit `position: fixed` hängt
 * am LAYOUT-Viewport, und der schrumpft auf iOS nicht, wenn die Tastatur
 * aufgeht — Safari verschiebt nur den sichtbaren Ausschnitt. Ein Fenster, das
 * unten am Rand klebt, liegt damit hinter der Tastatur, und der Browser kann
 * es auch nicht hereinscrollen: Es ist ja fixiert. Die Eingabezeile, in die
 * man gerade tippt, ist dann unsichtbar.
 *
 * Für normale, mitfließende Composer (wie auf `/fragen`) stellt sich die
 * Frage nicht — die scrollt der Browser von selbst ins Bild. Deshalb steht
 * diese Datei hier und nicht in einem allgemeinen Layout-Hook.
 *
 * Gemessen wird über `window.visualViewport`: die Differenz zwischen dem
 * Layout-Viewport und dem, was davon noch zu sehen ist.
 */

/** Unter dieser Höhe ist es keine Tastatur, sondern eine ein-/ausfahrende
 *  Adressleiste — die darf nichts verschieben, sonst wackelt das Fenster beim
 *  Scrollen. */
const MINDESTHOEHE = 60;

/** Der verdeckte Streifen unten, in Pixeln. */
export function tastaturHoehe(
  viewport: { height: number; offsetTop: number } | null | undefined,
  fensterHoehe: number,
): number {
  if (!viewport || !(fensterHoehe > 0)) return 0;
  const verdeckt = fensterHoehe - (viewport.height + viewport.offsetTop);
  if (!Number.isFinite(verdeckt) || verdeckt < MINDESTHOEHE) return 0;
  // Nie mehr als der halbe Bildschirm: Ein Ausreißer (Zoom, Seitenleiste
  // eines fremden Browsers) soll das Fenster nicht aus dem Bild schieben.
  return Math.round(Math.min(verdeckt, fensterHoehe / 2));
}
