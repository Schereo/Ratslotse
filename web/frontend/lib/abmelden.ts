/** Wer bewusst abmeldet, will auf die Anmeldung — nicht zurück auf die Seite,
 *  auf der er gerade stand.
 *
 *  Die App-Hülle schickt jeden, dessen Konto plötzlich fehlt, zur Anmeldung
 *  und hängt das bisherige Ziel als `?weiter=` an (Sitzung abgelaufen: danach
 *  soll es dort weitergehen). Beim Abmelden lief genau dieser Weg mit — man
 *  landete auf `/login?weiter=%2Faccount`, als wäre die Sitzung abgelaufen.
 *  Die Abmeldung hinterlässt deshalb eine Marke, die die Hülle einmal abholt. */
const SCHLUESSEL = "ratslotse.abgemeldet";

export function abmeldenMerken(): void {
  try { sessionStorage.setItem(SCHLUESSEL, "1"); } catch { /* ohne Speicher: dann eben mit Ziel */ }
}

export function abmeldenAbholen(): boolean {
  try {
    const da = sessionStorage.getItem(SCHLUESSEL) === "1";
    if (da) sessionStorage.removeItem(SCHLUESSEL);
    return da;
  } catch {
    return false;
  }
}
