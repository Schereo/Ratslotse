/** Ob eine Frage aus `/fragen?q=…&chip=1` wirklich angetippt wurde.
 *
 *  Die Marke `chip=1` in der Adresse kann jeder Link setzen. Bis 10/2026
 *  stellte die Fragen-Seite eine solche Frage sofort — im Namen dessen, der den
 *  Link öffnete: Fragelimit verbraucht, fremde Fragen in „Meine Gespräche"
 *  (zweite Sicherheitsprüfung, F4). Jetzt legt der Chip beim Antippen eine
 *  einmalige Marke in den sessionStorage dieses Tabs; die Fragen-Seite löst
 *  sie ein. Ohne Marke wird nur vorbelegt.
 *
 *  Zehn Minuten Gültigkeit, damit der Umweg über die Anmeldung reicht.
 *  sessionStorage gehört dem Tab, eine fremde Seite kommt nicht heran.
 */
const SCHLUESSEL = "ratslotse:chip-frage";
const GUELTIG_MS = 10 * 60 * 1000;

export function chipMerken(frage: string): void {
  try {
    sessionStorage.setItem(SCHLUESSEL, JSON.stringify({ frage, zeit: Date.now() }));
  } catch { /* privates Fenster: dann eben nur vorbelegen */ }
}

/** Wurde GENAU diese Frage eben angetippt? Löst die Marke ein (einmalig). */
export function chipEinloesen(frage: string): boolean {
  try {
    const roh = sessionStorage.getItem(SCHLUESSEL);
    if (!roh) return false;
    sessionStorage.removeItem(SCHLUESSEL);
    const marke = JSON.parse(roh) as { frage?: unknown; zeit?: unknown };
    return marke.frage === frage && typeof marke.zeit === "number"
      && Date.now() - marke.zeit < GUELTIG_MS;
  } catch {
    return false;
  }
}
