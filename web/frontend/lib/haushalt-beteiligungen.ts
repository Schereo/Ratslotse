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
  /** Hielt die Rechenprobe „gleich viele Namen wie Funktionen"? Nur dann
   *  trägt eine Person ihr Amt (s. `aufsichtspersonen`). Optional, weil eine
   *  ältere API das Feld nicht kennt — dann gilt „unbekannt", nicht „ja". */
  funktionen_zuordenbar?: boolean;
};

/** Ein Mitglied des Aufsichtsorgans — Betriebsausschuss, Aufsichtsrat oder
 *  Verwaltungsrat, je nach Rechtsform.
 *
 *  `funktion` ist `null`, wo der Bericht die Zuordnung nicht hergibt: Er
 *  listet Namen und Funktionen in zwei getrennten Spalten, die sich nur nach
 *  Position paaren lassen — und das ist nur erlaubt, wenn beide Listen exakt
 *  gleich lang sind. `null` heißt deshalb **unbekannt**, nie „keine". Der
 *  Vorsitz steht dagegen in der Namenszeile selbst („…, Vorsitzende") und
 *  bleibt auch dann bekannt, wenn die Paarung scheitert. */
export type Aufsichtsperson = {
  gesellschaft: string;
  /** Wie das Organ im Bericht heißt — aus der Kopfzeile der Liste. */
  gremium: string | null;
  name: string;
  funktion: string | null;
  vorsitz: "vorsitz" | "stellvertretung" | null;
  /** Klammerzusatz aus dem Bericht, etwa „bis 30. Juni 2022". */
  hinweis: string | null;
  /** Als **Ratsmitglied** im Personenverzeichnis gefunden — dann führt der
   *  Name auf die Personen-Seite. `null` heißt: kein Link. Das ist mehr als
   *  „nicht gefunden": Verwaltungsleute und die Aufsichtsorgane selbst stehen
   *  zwar im Verzeichnis, haben aber keine Seite (nur Mandatsträger*innen
   *  haben eine) — sie bleiben deshalb bewusst unverlinkt. */
  slug: string | null;
  partei: string | null;
  reihenfolge: number;
  herkunft_id: number | null;
};

/** Wem die Gesellschaft gehört — eine Zeile der Tabelle aus Abschnitt 2.
 *
 *  Beide Zahlen können fehlen, weil nicht jeder Bericht beide nennt. Die
 *  Summenzeile („Stammkapital") ist die Probe und steht hier NICHT: Sie ist
 *  kein Eigentümer. Fällt die Probe, liefert die API für diese Gesellschaft
 *  gar keine Eigentümer — dann steht der Rohtext des Abschnitts da. */
export type Eigentuemer = {
  gesellschaft: string;
  name: string;
  amount_eur: number | null;
  share_pct: number | null;
  reihenfolge: number;
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
  year: number;
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
  year: number;
  konzern_beitrag: number;
  jahresergebnis: number;
  difference: number;
};

export type BeteiligungsDaten = {
  berichtsjahre: number[];
  jahre: number[];
  gesellschaften: Gesellschaft[];
  texte: Textabschnitt[];
  kennzahlen: Kennzahl[];
  konzernvergleich: Konzernzeile[];
  /** Optional, und das ist die ganze Fallback-Logik der Seite: Wo die Liste
   *  fehlt (ältere API) oder für eine Gesellschaft leer bleibt (Probe nicht
   *  bestanden), steht der Rohtext des Abschnitts — nie ein leerer Block. */
  personen?: Aufsichtsperson[];
  eigentuemer?: Eigentuemer[];
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
  for (const liste of aus.values()) liste.sort((a, b) => a.year - b.year);
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
    if (!treffer || k.year > treffer.year) treffer = k;
  }
  return treffer;
}

export function textVon(daten: BeteiligungsDaten | null, gesellschaft: string,
                        abschnitt: string): Textabschnitt | null {
  return (daten?.texte ?? []).find(
    (t) => t.gesellschaft === gesellschaft && t.abschnitt === abschnitt) ?? null;
}

/** Der erste Satz des Unternehmensgegenstands — für die Karte in der Liste.
 *  Abgeschnitten wird am Satzende, nicht nach n Zeichen. */
export function auftragSatz(daten: BeteiligungsDaten, g: Gesellschaft): string | null {
  const gegenstand = textVon(daten, g.gesellschaft, "gegenstand");
  if (!gegenstand) return null;
  const glatt = gegenstand.text.replace(/\s+/g, " ");
  return glatt.match(/^.{20,200}?\.(?=\s|$)/)?.[0] ?? glatt.slice(0, 160);
}

/** Ein langer Abschnitt in „was man zuerst sieht" und „der Rest".
 *
 *  Geschnitten wird am Absatz, wo es einen gibt: Die Verwaltung setzt ihre
 *  Absätze selbst, und der erste sagt in aller Regel, worum es geht. Fehlt
 *  eine Absatzmarke, endet die Vorschau am letzten Satzende vor der Grenze —
 *  ein Schnitt mitten im Wort läse sich wie ein Ladefehler.
 *
 *  Der Rest verschwindet nie ersatzlos, sondern hinter einem Auslöser
 *  („Ganzen Wortlaut zeigen", H4-A) — die Seite kürzt die Verwaltung nicht. */
export function absatzVorschau(text: string, grenze = 420): { kopf: string; rest: string } {
  const glatt = text.replace(/\r/g, "").trim();
  const absatz = glatt.indexOf("\n");
  if (absatz > 0 && absatz <= grenze * 1.6) {
    return { kopf: glatt.slice(0, absatz).trim(), rest: glatt.slice(absatz).trim() };
  }
  if (glatt.length <= grenze) return { kopf: glatt, rest: "" };
  const satz = glatt.lastIndexOf(". ", grenze);
  const schnitt = satz > grenze * 0.5 ? satz + 1 : glatt.lastIndexOf(" ", grenze);
  return { kopf: glatt.slice(0, schnitt).trim(), rest: glatt.slice(schnitt).trim() };
}

/** Der Pflicht-Satz unter der Zahl (GB-00 `<Einordnung>`): berichtet,
 *  bewertet nicht. Wo die Daten eine Aussage tragen, kommt sie aus den Daten
 *  (Gesamtabschluss-Abgleich, Ergebnisabführung); für die Betriebe, deren
 *  Auftrag die Zahl sonst verzerrte, steht die redaktionelle Einordnung der
 *  H3-Boards. Der Rückfall-Satz sagt ehrlich, dass die Zahl allein nichts
 *  benotet. */
export function einordnungFuer(daten: BeteiligungsDaten, g: Gesellschaft,
                               ergebnisse: Kennzahl[]): string {
  const redaktionell: Record<string, string> = {
    vwg: "Ein Verkehrsbetrieb mit Verlust erfüllt seinen Auftrag — Busfahren soll "
      + "bezahlbar sein, nicht profitabel.",
    gsg: "Überschüsse bleiben im Unternehmen und finanzieren Neubau und Sanierung.",
  };
  if (redaktionell[g.gesellschaft]) return redaktionell[g.gesellschaft];

  if (ergebnisse.length >= 2 && ergebnisse.every((k) => k.wert === 0)) {
    return "Die Null ist Vertragslage, kein Stillstand: Der Betrieb führt sein "
      + "Ergebnis an die Stadt ab oder bekommt es ausgeglichen.";
  }
  const juengstes = ergebnisse[ergebnisse.length - 1];
  const vergleich = daten.konzernvergleich.find((z) => z.gesellschaft === g.gesellschaft);
  if (juengstes && vergleich && vergleich.year === juengstes.year
      && Math.abs(vergleich.difference) <= 1000) {
    return "Der Betrag ist deckungsgleich mit dem Gesamtabschluss — zwei Quellen, "
      + "eine Zahl.";
  }
  return "Gewinn oder Verlust ist hier keine Note — welchen Auftrag die "
    + "Gesellschaft damit erfüllt, steht in ihrem Steckbrief.";
}

// --- Aufsichtsorgane und Eigentümer -----------------------------------------

/** Die Mitglieder des Aufsichtsorgans, in der Reihenfolge des Berichts. */
export function aufsichtspersonen(daten: BeteiligungsDaten | null,
                                  gesellschaft: string): Aufsichtsperson[] {
  return (daten?.personen ?? [])
    .filter((p) => p.gesellschaft === gesellschaft)
    .sort((a, b) => a.reihenfolge - b.reihenfolge);
}

/** Wie das Organ im Bericht heißt („Betriebsausschuss", „Aufsichtsrat").
 *  Nennen mehrere Zeilen verschiedene Organe, gewinnt keines — dann steht
 *  die neutrale Überschrift des Abschnitts. */
export function gremiumName(personen: Aufsichtsperson[]): string | null {
  const namen = new Set(personen.map((p) => p.gremium).filter(Boolean));
  return namen.size === 1 ? ([...namen][0] as string) : null;
}

export type Aufsichtsgruppe = {
  key: string;
  /** Überschrift der Gruppe — das Wort des Berichts, nicht unseres. */
  titel: string;
  personen: Aufsichtsperson[];
};

/** Rang der Gruppen: Vorsitz zuerst, dann der Rat, dann die Belegschaft,
 *  dann alles Übrige, zuletzt die ohne bekanntes Amt. */
function gruppenRang(key: string): number {
  if (key === "vorsitz") return 0;
  if (key === "") return 4;
  if (/ratsmitglied|rat der stadt|ratsherr|ratsfrau/i.test(key)) return 1;
  if (/beschäftigt|arbeitnehmer|personalrat|betriebsrat|belegschaft/i.test(key)) return 2;
  return 3;
}

/** Die Mitglieder nach Funktion gebündelt.
 *
 *  Gruppiert wird nach dem **Wortlaut** des Berichts („Ratsmitglied",
 *  „Beschäftigtenvertreterin"): Eigene Oberbegriffe zu erfinden hieße, eine
 *  Einteilung zu behaupten, die die Quelle nicht trifft. Der Vorsitz ist die
 *  einzige Ausnahme — er steht in der Namenszeile und ist deshalb auch dann
 *  bekannt, wenn die Ämter es nicht sind.
 *
 *  `zuordenbar === false` heißt: Die Ämter sind unbekannt. Dann gibt es genau
 *  eine Gruppe (plus Vorsitz), und die Seite sagt daneben, warum. */
export function aufsichtsgruppen(personen: Aufsichtsperson[],
                                 zuordenbar: boolean): Aufsichtsgruppe[] {
  const nach = new Map<string, Aufsichtsperson[]>();
  for (const p of personen) {
    const key = p.vorsitz ? "vorsitz" : ((zuordenbar && p.funktion) || "");
    nach.set(key, [...(nach.get(key) ?? []), p]);
  }
  return [...nach.entries()]
    .map(([key, liste]) => ({
      key,
      titel: key === "vorsitz" ? "Vorsitz" : key || "Weitere Mitglieder",
      // Im Vorsitz steht die Vorsitzende vor ihrer Stellvertretung, sonst
      // bleibt die Reihenfolge des Berichts.
      personen: key === "vorsitz"
        ? [...liste].sort((a, b) => (a.vorsitz === "vorsitz" ? 0 : 1) - (b.vorsitz === "vorsitz" ? 0 : 1))
        : liste,
    }))
    .sort((a, b) => gruppenRang(a.key) - gruppenRang(b.key) || a.titel.localeCompare(b.titel, "de"));
}

/** Die Eigentümer, in der Reihenfolge des Berichts. */
export function eigentuemerVon(daten: BeteiligungsDaten | null,
                               gesellschaft: string): Eigentuemer[] {
  return (daten?.eigentuemer ?? [])
    .filter((e) => e.gesellschaft === gesellschaft)
    .sort((a, b) => a.reihenfolge - b.reihenfolge);
}

/** Der Anteil der Stadt Oldenburg an einer Gesellschaft, in Prozent.
 *
 *  Kommt aus der Gesellschaftertabelle des Berichts (`council_gesellschaft_
 *  eigentuemer`), die nur übernommen wird, wenn ihre Probe hält: Summe der
 *  Prozente = 100 ± 0,5 UND Summe der Beträge = Stammkapital. Was hier steht,
 *  ist also gedruckt und nachgerechnet — nicht aus dem Fließtext geschätzt.
 *
 *  `null` heißt „der Bericht nennt für diese Gesellschaft keine Quote": bei
 *  der TGO Besitz führt er statt Anteilseignern nur Entsendungsrechte. Eine
 *  fehlende Quote als „0 %" zu zeigen wäre eine Falschaussage. */
export function stadtAnteil(daten: BeteiligungsDaten | null,
                            gesellschaft: string): number | null {
  const zeile = eigentuemerVon(daten, gesellschaft)
    .find((e) => /^Stadt Oldenburg\b/.test(e.name.trim()));
  return zeile?.share_pct ?? null;
}

/** Hält die Stadt weniger als die Hälfte?
 *
 *  Die Schwelle ist keine Design-Setzung, sondern die Grenze, an der die
 *  Stadt ihre Mehrheit in der Gesellschafterversammlung verliert. Im Bestand
 *  trifft das drei Gesellschaften: GSG 34,5 %, GOL 16,67 % und — knapp
 *  darüber und deshalb NICHT betroffen — die VWG mit 74 %. */
export function istMinderheit(anteil: number | null): boolean {
  return anteil !== null && anteil < 50;
}

/** Das Gewicht einer Zeile im Anteilsstreifen.
 *
 *  Prozent, wo der Bericht Prozent nennt, sonst der Betrag — die Breite ist
 *  Geometrie, nicht Aussage. Angeschrieben wird ausschließlich, was in der
 *  Quelle steht; eine aus dem Betrag gerechnete Quote bekäme sonst dieselbe
 *  Autorität wie eine gedruckte. */
export function anteilsGewicht(e: Eigentuemer): number {
  return e.share_pct ?? e.amount_eur ?? 0;
}

/** Euro-Betrag, kompakt und ohne Bewertung.
 *
 *  KEIN Vorzeichen-Farbcode und keine Pfeile: Ein Verkehrsbetrieb, der Verlust
 *  macht, erfüllt seinen Auftrag — dieselbe Begründung wie in
 *  `components/grafik/hantel.tsx`. Das Minus steht da, weil es zur Zahl
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

// --- Rechtsform (H3-02: die Formen-Sprache der Konzernkarte) ----------------

/** Die drei Formen, die der Bericht selbst unterscheidet.
 *
 *  „Minderheitsanteil" ist bewusst KEINE vierte Form: Eine Rechtsform sagt,
 *  wie eine Einheit verfasst ist, ein Anteil sagt, wie viel davon der Stadt
 *  gehört. Beides in eine Aufzählung zu werfen hieße, eine GmbH mit 34 %
 *  könne keine GmbH mehr sein. Die Quote steht deshalb als eigenes Zeichen
 *  neben der Form (`stadtAnteil`, `istMinderheit`) — seit die
 *  Gesellschaftertabelle mit Probe gelesen wird. */
export type Rechtsform = "eigenbetrieb" | "aoer" | "gesellschaft";

export const RECHTSFORM_TITEL: Record<Rechtsform, string> = {
  eigenbetrieb: "Eigenbetrieb",
  aoer: "Anstalt öffentlichen Rechts",
  gesellschaft: "GmbH / Co. KG",
};

/** Rechtsform aus der Gliederungsnummer des Berichts — deterministisch, aus
 *  der Quelle statt geraten: Der Bericht gliedert seine Abschnitte selbst
 *  nach Rechtsform (Inhaltsverzeichnis, geprüft am Bericht 2023):
 *
 *    2.2 Eigenbetriebe · 2.3 Kommunale Anstalten des öffentlichen Rechts
 *    · 2.4 Privatrechtliche Organisationsformen
 *
 *  Der Name allein taugt nicht („Abfallwirtschaftsbetrieb Stadt Oldenburg"
 *  trägt sein „Eigenbetrieb" nicht im Namen). Eine unbekannte Gruppe liefert
 *  `null` — dann rendert die Karte KEINE Form statt einer falschen. */
export function rechtsform(g: Pick<Gesellschaft, "gliederung">): Rechtsform | null {
  const gruppe = g.gliederung.split(".")[1];
  if (gruppe === "2") return "eigenbetrieb";
  if (gruppe === "3") return "aoer";
  if (gruppe === "4") return "gesellschaft";
  return null;
}
