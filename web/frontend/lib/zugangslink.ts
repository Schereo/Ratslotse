/**
 * Anmeldelinks aus Mails (`kern/zugangslink.py`): `?ml=<token>` an einem
 * Link der Release-Ankündigung.
 *
 * Wer nicht angemeldet ist, landet über die Hülle auf `/login?weiter=…`, und
 * das Token steckt im Ziel. Die Anmeldeseite bietet dann EINEN Knopf an, der
 * es einlöst — bewusst kein automatischer Aufruf: Mail-Scanner öffnen Links
 * vorab und führen dabei auch Skripte aus. Gilt das Token nicht mehr, bleibt
 * das gewöhnliche Formular, und nach der Anmeldung geht es zum selben Ziel.
 */
import { useEffect } from "react";
import { sicheresZiel } from "./public-routes";

export const ZUGANG_PARAM = "ml";

/** Aus einem Rücksprungziel das Token und das Ziel ohne Token. */
export function zugangAus(weiter: string | null | undefined): { token: string; ziel: string } | null {
  const ziel = sicheresZiel(weiter);
  if (!ziel) return null;
  const url = new URL(ziel, "https://ratslotse.invalid");
  const token = url.searchParams.get(ZUGANG_PARAM);
  if (!token || token.length < 20 || token.length > 800) return null;
  url.searchParams.delete(ZUGANG_PARAM);
  return { token, ziel: `${url.pathname}${url.search}${url.hash}` };
}

/** Eine Adresse ohne das Token — für die Adresszeile und für `weiter=`. */
export function ohneZugang(pfadMitQuery: string): string {
  const url = new URL(pfadMitQuery, "https://ratslotse.invalid");
  if (!url.searchParams.has(ZUGANG_PARAM)) return pfadMitQuery;
  url.searchParams.delete(ZUGANG_PARAM);
  return `${url.pathname}${url.search}${url.hash}`;
}

/** Wer schon angemeldet ist und einen Link aus der Mail öffnet, braucht das
 *  Token nicht — es verschwindet still aus der Adresszeile (und damit aus
 *  Lesezeichen, geteilten Links und dem Verlauf). */
export function useZugangAusAdresseRaeumen(): void {
  useEffect(() => {
    const jetzt = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const sauber = ohneZugang(jetzt);
    if (sauber !== jetzt) window.history.replaceState(window.history.state, "", sauber);
  }, []);
}
