// Ist-Investitionen (/haushalt/gebaut) — Typen und Rechenwege.
//
// DIE REGEL, DIE DIESE DATEI TRÄGT: Es gibt hier zwei Reihen, nicht eine.
// Zum 01.01.2010 stellte die Stadt von kameraler auf doppische Buchführung um;
// das Statistische Jahrbuch führt deshalb zwei Tabellen und begründet den
// Schnitt in einer Fußnote. Keine Funktion dieser Datei bildet eine Summe, ein
// Mittel oder eine Veränderung ÜBER diesen Schnitt hinweg — `reihen()` teilt
// die Daten als Erstes, und alles Weitere rechnet innerhalb einer Reihe.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

/** Eine Auszahlungsart mit ihrer Überschrift AUS DER QUELLE. Der Titel reist
 *  mit der Zeile, statt hier zu stehen: Die beiden Rechnungswesen benennen
 *  ihre Arten verschieden, und eine Liste im Frontend wäre die zweite,
 *  konkurrierende Wahrheit. */
export type Art = { feld: string; titel: string; betrag: number };

export type GebautJahr = {
  jahr: number;
  /** `"kameral"` (bis 2009) oder `"doppik"` (ab 2010). */
  regelwerk: string;
  /** Die ausgewiesene Summenspalte in Euro. */
  insgesamt: number;
  arten: Art[];
  herkunft_id: number | null;
};

export type GebautDaten = {
  reihe: GebautJahr[];
  jahre: number[];
  /** Was diese Zahlen zählen — kommt aus `council/investitionen_ist.py`,
   *  damit Oberfläche und Datenbank dieselbe Auskunft geben. */
  abgrenzung: string;
  regelwerke: { schluessel: string; titel: string }[];
  /** Jahre, die INNERHALB einer Reihe fehlen, je Regelwerk. Sie sind nicht
   *  null, sondern unbelegt: Ihre Zeilensumme geht in der Quelle selbst nicht
   *  auf, und anders als bei den Schulden gibt es keine zweite Probe, die
   *  wenigstens die Summe trüge. */
  fehlend: Record<string, number[]>;
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(daten: GebautDaten | null, id: number | null): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

export type Reihe = {
  schluessel: string;
  titel: string;
  jahre: GebautJahr[];
  /** Was in dieser Reihe fehlt — bereits als Jahreszahlen. */
  fehlend: number[];
};

/** Die Daten nach Rechnungswesen getrennt, in der Reihenfolge des Backends.
 *
 *  Die zentrale Funktion dieser Datei: Sie ist der Grund, warum keine
 *  Darstellung versehentlich über 2009/2010 hinweg rechnet. Leere Reihen
 *  fallen weg — eine Überschrift ohne Zahlen wäre ein Versprechen. */
export function reihen(daten: GebautDaten | null): Reihe[] {
  if (!daten) return [];
  return daten.regelwerke
    .map((r) => ({
      schluessel: r.schluessel,
      titel: r.titel,
      jahre: daten.reihe.filter((z) => z.regelwerk === r.schluessel),
      fehlend: daten.fehlend[r.schluessel] ?? [],
    }))
    .filter((r) => r.jahre.length > 0);
}

/** Die jüngste Reihe — die, auf die sich die große Zahl im Kopf bezieht.
 *
 *  Nicht „die doppische": Der Schlüssel steht im Backend, und wenn die Stadt
 *  eines Tages ein drittes Rechnungswesen einführt, soll diese Seite die
 *  neueste Reihe zeigen und nicht eine, die im Frontend festgenagelt ist. */
export function juengsteReihe(daten: GebautDaten | null): Reihe | null {
  const alle = reihen(daten);
  if (!alle.length) return null;
  return alle.reduce((a, b) =>
    (b.jahre[b.jahre.length - 1].jahr > a.jahre[a.jahre.length - 1].jahr ? b : a));
}

/** Der größte Posten eines Jahrgangs — gerechnet, nicht beschriftet.
 *
 *  Eine Seite, die „die meisten Mittel gehen in Baumaßnahmen" als Text trägt,
 *  wird mit dem nächsten Jahrgang still falsch: 2025 ist es „Sonstige
 *  Investitionstätigkeit", 2016 war es „bewegliches Sachvermögen". */
export function groessterPosten(z: GebautJahr | null): Art | null {
  if (!z || !z.arten.length) return null;
  return z.arten.reduce((a, b) => (b.betrag > a.betrag ? b : a));
}

/** Alle Auszahlungsarten einer Reihe, in der Spaltenfolge der Quelle — die
 *  Legende einer Reihe.
 *
 *  Aus den Daten und nicht aus einer Konstante: Käme eine Art dazu oder fiele
 *  eine weg, stünde die Legende sonst gegen die Balken. */
export function artenDerReihe(r: Reihe | null): { feld: string; titel: string }[] {
  if (!r) return [];
  const gesehen = new Map<string, string>();
  for (const z of r.jahre) {
    for (const a of z.arten) if (!gesehen.has(a.feld)) gesehen.set(a.feld, a.titel);
  }
  return [...gesehen].map(([feld, titel]) => ({ feld, titel }));
}

/** Deutsche Anzeige eines Euro-Betrags in Millionen, eine Nachkommastelle. */
export function deMioEuro(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return (v / 1e6).toLocaleString("de-DE",
    { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}
