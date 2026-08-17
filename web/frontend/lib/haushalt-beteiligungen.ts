// Die städtischen Gesellschaften aus dem Beteiligungsbericht — Typen und die
// Rechnungen, die die Seite braucht.
//
// Getrennt von der Seite, weil hier nichts gerendert wird und beides sonst
// zusammen wüchse: Die Seite zeigt eine Liste und einen Steckbrief, die
// Zuordnung „welche Kennzahl gehört zu welcher Gesellschaft, in welchem Jahr,
// aus welchem Bericht" ist Rechnerei und gehört nicht zwischen JSX.
//
// EINE REGEL ZIEHT SICH DURCH: Die Zeitreihe ist lückenhaft, und das ist kein
// Fehler. Ein Wert kommt nur in den Bestand, wenn ihn eine Rechenprobe deckt
// (`council/beteiligungsbericht.py`); die Eigenkapitalquote des jüngsten
// Jahres etwa hat keine und fehlt deshalb. Wer hier interpoliert oder den
// letzten bekannten Wert fortschreibt, erfindet Zahlen. Die Seite zeigt
// stattdessen, was da ist, und lässt die Lücke Lücke sein.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type Gesellschaft = {
  bericht_jahr: number;
  gesellschaft: string;
  name: string;
  gliederung: string;
  seite: number | null;
  konzern_key: string | null;
  herkunft_id: number | null;
};

export type Textabschnitt = {
  bericht_jahr: number;
  gesellschaft: string;
  abschnitt: string;
  text: string;
  herkunft_id: number | null;
};

export type Kennzahl = {
  gesellschaft: string;
  kennzahl: "jahresergebnis" | "bilanzsumme" | "eigenkapitalquote";
  jahr: number;
  wert: number;
  einheit: "eur" | "prozent";
  bericht_jahr: number;
  /** In wie vielen Berichten dieser Wert übereinstimmend steht. */
  berichte: number;
  herkunft_id: number | null;
};

export type Konzernzeile = {
  gesellschaft: string;
  name: string;
  jahr: number;
  konzern_beitrag: number;
  jahresergebnis: number;
  differenz: number;
};

export type BeteiligungsDaten = {
  berichtsjahre: number[];
  jahre: number[];
  gesellschaften: Gesellschaft[];
  texte: Textabschnitt[];
  kennzahlen: Kennzahl[];
  konzernvergleich: Konzernzeile[];
  herkunft: Record<string, Herkunft>;
};

/** Überschriften der beschreibenden Abschnitte, in der Reihenfolge des
 *  Berichts. Der Schlüssel kommt aus `beteiligungsbericht.TEXTABSCHNITTE`;
 *  die Wortwahl hier ist die für Leserinnen, nicht die amtliche
 *  („Besetzung der Aufsichtsorgane" → „Wer sie beaufsichtigt"). */
export const ABSCHNITTE: { key: string; titel: string }[] = [
  { key: "gegenstand", titel: "Was die Gesellschaft tut" },
  { key: "beteiligungsverhaeltnisse", titel: "Wem sie gehört" },
  { key: "aufsichtsorgane", titel: "Wer sie beaufsichtigt" },
  { key: "beteiligungen", titel: "Woran sie selbst beteiligt ist" },
  { key: "haushalt", titel: "Was sie für den städtischen Haushalt bedeutet" },
];

export const KENNZAHL_TITEL: Record<Kennzahl["kennzahl"], string> = {
  jahresergebnis: "Jahresergebnis",
  bilanzsumme: "Bilanzsumme",
  eigenkapitalquote: "Eigenkapitalquote",
};

export function herkunftVon(daten: BeteiligungsDaten | null, id: number | null | undefined) {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

/** Die Kennzahlen einer Gesellschaft, nach Kennzahl gebündelt und je Reihe
 *  nach Jahr sortiert. */
export function reihen(daten: BeteiligungsDaten | null, gesellschaft: string) {
  const aus = new Map<Kennzahl["kennzahl"], Kennzahl[]>();
  for (const k of daten?.kennzahlen ?? []) {
    if (k.gesellschaft !== gesellschaft) continue;
    const liste = aus.get(k.kennzahl) ?? [];
    liste.push(k);
    aus.set(k.kennzahl, liste);
  }
  for (const liste of aus.values()) liste.sort((a, b) => a.jahr - b.jahr);
  return aus;
}

/** Der jüngste Wert einer Kennzahl — für die Listenansicht.
 *
 *  „Jüngster vorhandener", nicht „jüngstes Berichtsjahr": Die Großleitstelle
 *  führt noch im Bericht für 2024 die Jahre bis 2021, weil ihr Abschluss
 *  später vorlag. Wer stur das Berichtsjahr abfragt, zeigt für sie nichts —
 *  obwohl fünf Jahre danebenstehen. */
export function juengster(daten: BeteiligungsDaten | null, gesellschaft: string,
                          kennzahl: Kennzahl["kennzahl"]): Kennzahl | null {
  let treffer: Kennzahl | null = null;
  for (const k of daten?.kennzahlen ?? []) {
    if (k.gesellschaft !== gesellschaft || k.kennzahl !== kennzahl) continue;
    if (!treffer || k.jahr > treffer.jahr) treffer = k;
  }
  return treffer;
}

export function textVon(daten: BeteiligungsDaten | null, gesellschaft: string,
                        abschnitt: string): Textabschnitt | null {
  return (daten?.texte ?? []).find(
    (t) => t.gesellschaft === gesellschaft && t.abschnitt === abschnitt) ?? null;
}

/** Euro-Betrag, kompakt und ohne Bewertung.
 *
 *  KEIN Vorzeichen-Farbcode und keine Pfeile: Ein Verkehrsbetrieb, der Verlust
 *  macht, erfüllt seinen Auftrag — dieselbe Begründung wie in
 *  `components/haushalt/hantel.tsx`. Das Minus steht da, weil es zur Zahl
 *  gehört, nicht als Urteil. */
export function eur(wert: number): string {
  const abs = Math.abs(wert);
  if (abs >= 1_000_000) {
    return `${(wert / 1_000_000).toLocaleString("de-DE", {
      minimumFractionDigits: 1, maximumFractionDigits: 1 })} Mio. €`;
  }
  if (abs >= 1_000) {
    return `${(wert / 1_000).toLocaleString("de-DE", {
      maximumFractionDigits: 0 })} Tsd. €`;
  }
  return `${wert.toLocaleString("de-DE", { maximumFractionDigits: 2 })} €`;
}

export function prozent(wert: number): string {
  return `${wert.toLocaleString("de-DE", {
    minimumFractionDigits: 1, maximumFractionDigits: 2 })} %`;
}

export function wertText(k: Kennzahl): string {
  return k.einheit === "prozent" ? prozent(k.wert) : eur(k.wert);
}

/** Die Gesellschaften, sortiert wie im Bericht (Eigenbetriebe, Anstalten,
 *  privatrechtliche) — die Gliederungsnummer trägt diese Ordnung schon. */
export function sortiert(daten: BeteiligungsDaten | null): Gesellschaft[] {
  return [...(daten?.gesellschaften ?? [])].sort((a, b) =>
    a.gliederung.localeCompare(b.gliederung, "de", { numeric: true }));
}
