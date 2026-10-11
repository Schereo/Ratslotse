/** Was nach dem Abmelden nicht im Browser liegen bleiben darf.
 *
 *  Der Tab überlebt das Abmelden — und mit ihm, was das Konto dort
 *  zwischengespeichert hat. Bis 10/2026 sah, wer sich danach im selben Tab
 *  anmeldete, Lottis letzten Verlauf des vorigen Kontos, und in der App-Hülle
 *  lag der Abfrage-Cache noch 24 Stunden im localStorage (zweite
 *  Sicherheitsprüfung, F8/F17).
 */

/** Gespräche und ihre Zuordnung — gehören dem Konto, nicht dem Tab. */
const GESPRAECHE = [
  "ratslotse:lotti-verlauf",
  "ratslotse:lotti-gespraech",
  "ratslotse:qa-gespraech",
  "ratslotse:qa-hat-gespraeche",
];
/** Der gerettete Entwurf: beim Ablauf der Sitzung behalten (er soll nach der
 *  Anmeldung zurückkommen), beim Abmelden weg. */
const ENTWURF = "ratslotse:entwurf";
/** Der gespeicherte Abfrage-Cache der App-Hülle (app/providers.tsx). */
export const QUERY_CACHE = "ratslotse.query-cache";

export function kontoDatenRaeumen({ mitEntwurf }: { mitEntwurf: boolean }): void {
  const sitzung = [...GESPRAECHE, ...(mitEntwurf ? [ENTWURF] : [])];
  try {
    for (const k of sitzung) sessionStorage.removeItem(k);
  } catch { /* gesperrter Speicher: dort liegt dann auch nichts */ }
  try {
    localStorage.removeItem(QUERY_CACHE);
  } catch { /* dito */ }
}
