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

/* ---- Das Geheimnis aus dem Link ------------------------------------------- */

/* Es liegt im localStorage, nicht im sessionStorage: Wer noch kein Konto hat,
   registriert sich und bestätigt die Adresse über einen Link aus der Mail —
   der öffnet einen NEUEN Tab, und den sessionStorage des alten sieht er nicht.
   Damit es auf einem geteilten Gerät nicht herumliegt: höchstens 48 Stunden
   (wer länger braucht, öffnet den Link noch einmal), gebunden an das erste
   Konto, das die Seite damit öffnet, weg beim Beitreten, wenn die Einladung
   nicht mehr gilt, und beim Abmelden (`lib/konto-raeumen.ts`). */
const GEHEIMNIS_STUNDEN = 48;
const PRAEFIX = "ratslotse:einladung:";

interface Gemerkt { s: string; at: number; owner?: number }

function lesen(id: string): Gemerkt | null {
  try {
    const v = JSON.parse(localStorage.getItem(PRAEFIX + id) ?? "null") as Gemerkt | null;
    return v && typeof v.s === "string" && typeof v.at === "number" ? v : null;
  } catch {
    return null;
  }
}

export function geheimnisMerken(id: string, s: string, now = Date.now()): void {
  try { localStorage.setItem(PRAEFIX + id, JSON.stringify({ s, at: now })); } catch { /* privat */ }
  try { sessionStorage.setItem(PRAEFIX + id, s); } catch { /* privat */ }
  offeneEinladungMerken(`/notiz-einladung?i=${encodeURIComponent(id)}`);
}

/** Das Geheimnis für dieses Konto (``null`` ohne Konto: noch nicht gebunden).
 *  Ein anderes Konto bekommt es nicht — und es fällt dabei weg. */
export function geheimnisLesen(id: string, owner: number | null, now = Date.now()): string | null {
  const v = lesen(id);
  if (v) {
    const alt = now - v.at >= GEHEIMNIS_STUNDEN * 3_600_000;
    const fremd = owner != null && v.owner != null && v.owner !== owner;
    if (alt || fremd) {
      geheimnisVergessen(id);
      return null;
    }
    if (owner != null && v.owner == null) {
      try { localStorage.setItem(PRAEFIX + id, JSON.stringify({ ...v, owner })); } catch { /* privat */ }
    }
    return v.s;
  }
  try { return sessionStorage.getItem(PRAEFIX + id); } catch { return null; }
}

export function geheimnisVergessen(id: string): void {
  try { localStorage.removeItem(PRAEFIX + id); } catch { /* privat */ }
  try { sessionStorage.removeItem(PRAEFIX + id); } catch { /* privat */ }
  offeneEinladungVergessen();
}

/** Beim Abmelden: alle gemerkten Einladungen weg. */
export function einladungenRaeumen(): void {
  for (const speicher of [() => localStorage, () => sessionStorage]) {
    try {
      const s = speicher();
      const weg: string[] = [];
      for (let i = 0; i < s.length; i++) {
        const k = s.key(i);
        if (k?.startsWith(PRAEFIX)) weg.push(k);
      }
      for (const k of weg) s.removeItem(k);
    } catch { /* privat */ }
  }
  offeneEinladungVergessen();
}
