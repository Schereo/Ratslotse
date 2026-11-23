/**
 * Wo das Ratsinformationssystem der Stadt Oldenburg liegt — die eine Stelle
 * im Frontend. Gegenstück zu `council/ris.py`; `tests/test_ris_adresse.py`
 * hält beide zusammen.
 *
 * Bis 11/2026 stand `https://buergerinfo.oldenburg.de` an rund vierzig Stellen
 * wörtlich im Code. Dann zog die Stadt nach `ratsinfo.oldenburg.de/bi` um
 * (Seiten `.asp` statt `.php`, die Nummern sind geblieben); der alte Host
 * leitet jede Adresse auf die Startseite um. Jeder der vierzig Links führte
 * damit ins Leere — und keiner meldete es.
 *
 * Adressen, die das Backend liefert (Anlagen, Vorlagen, Protokolle), sind dort
 * schon umgezogen. Hier stehen nur die, die das Frontend selbst baut.
 */
export const RIS_HOST = "ratsinfo.oldenburg.de";
export const RIS_BASE = `https://${RIS_HOST}/bi`;

/** Frühere Hosts — noch in alten Links und gespeicherten Texten. */
export const RIS_FRUEHER = ["buergerinfo.oldenburg.de"] as const;

/** Die Seite einer Sitzung (Tagesordnung, Dokumente). */
export const risSitzung = (ksinr: number) => `${RIS_BASE}/si0057.asp?__ksinr=${ksinr}`;
/** Die Seite einer Vorlage. */
export const risVorlage = (kvonr: number) => `${RIS_BASE}/vo0050.asp?__kvonr=${kvonr}`;
/** Ein Dokument (PDF). */
export const risDokument = (id: number) => `${RIS_BASE}/getfile.asp?id=${id}&type=do`;
/** Die Vorlagen-Recherche — für Belege ohne einzelnes Dokument. */
export const RIS_RECHERCHE = `${RIS_BASE}/vo0040.asp`;

/** Zeigt die Adresse aufs Ratsinformationssystem — heutiger oder früherer Host? */
export function istRis(url: string): boolean {
  const u = url.toLowerCase();
  return u.includes(RIS_HOST) || RIS_FRUEHER.some((h) => u.includes(h));
}
