/* Wer über eine Einladung zu einer gemeinsamen Notiz kommt, soll dort auch
   ankommen — auch wenn er erst ein Konto anlegen und die Adresse in einem
   neuen Tab bestätigen muss. Klein und ohne Abhängigkeiten: Das App-Layout
   (Einrichtungs-Assistent) und die Bestätigungsseite lesen es mit. */

/** sessionStorage: Nach dem Beitreten über eine Einladung wartet der
 *  Einrichtungs-Assistent eines neuen Kontos bis zum nächsten Besuch. */
export const EINRICHTUNG_SPAETER = "ratslotse:einrichtung-spaeter";

/** localStorage: die Einladungsseite, zu der es nach dem Bestätigen der
 *  Adresse zurückgeht (der Link aus der Mail öffnet einen neuen Tab). */
const OFFENE_EINLADUNG = "ratslotse:offene-einladung";

export function offeneEinladungMerken(pfad: string): void {
  try { localStorage.setItem(OFFENE_EINLADUNG, JSON.stringify({ pfad, at: Date.now() })); } catch { /* privat */ }
}

export function offeneEinladungVergessen(): void {
  try { localStorage.removeItem(OFFENE_EINLADUNG); } catch { /* privat */ }
}

/** Der Pfad, wenn er höchstens acht Tage alt ist und wirklich eine
 *  Einladungsseite meint — nie ein beliebiges Ziel. */
export function offeneEinladung(now = Date.now()): string | null {
  try {
    const v = JSON.parse(localStorage.getItem(OFFENE_EINLADUNG) ?? "null") as { pfad?: string; at?: number } | null;
    if (v?.pfad && typeof v.at === "number" && now - v.at < 8 * 86_400_000
      && /^\/notiz-einladung\?[ai]=[\w%-]+$/.test(v.pfad)) return v.pfad;
  } catch { /* privat oder kaputt */ }
  return null;
}
