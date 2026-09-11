/** „HH:MM" aus einem ISO-Zeitstempel, deutsche Zeit — für die Etiketten des
 *  Beamers („Nachgetippt 20:14"). Bewusst hier statt aus `lib/tipp.ts` (die
 *  Handy-Screens, ein anderer PR desselben Plans): Der Beamer soll ohne den
 *  fertig werden; sind beide auf `main`, bleibt eine Fassung. */
export function uhrzeitKurz(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}
