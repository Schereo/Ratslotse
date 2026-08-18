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

/** Ein Jahr, das die Reihe ankündigt und nicht belegt.
 *
 *  `differenz` ist die GEMESSENE Lücke in Euro (Auszahlungsarten minus
 *  ausgewiesene Summe, vorzeichenbehaftet) — sie kommt aus dem Ingest-Lauf,
 *  der den Jahrgang verworfen hat, und steht nirgends im Frontend. `null`,
 *  wo der Bestand keine Messung führt; dann nennt die Seite die Lücke ohne
 *  Betrag, statt einen zu erfinden. */
export type GebautLuecke = { jahr: number; differenz: number | null };

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
  fehlend: Record<string, GebautLuecke[]>;
  /** Was aus den Investitionen wurde — der Anlagenspiegel des
   *  Jahresabschlusses (Abschnitt 8.1). */
  anlagen?: Anlagen;
  herkunft: Record<string, Herkunft>;
};

/** Eine Zeile des Anlagenspiegels: eine Vermögensposition in einem Jahr.
 *
 *  Die Vorzeichen sind die des Dokuments: `abgaenge`, `abschreibung` und
 *  `abschr_ende` stehen negativ. Wer sie beim Anzeigen dreht, muss es überall
 *  tun — eine halb gedrehte Reihe ist schlimmer als eine ungedrehte. */
export type AnlagePosten = {
  jahr: number;
  /** Gliederung wie im Dokument: „1", „1.1", „2", „2.3" … */
  nr: string;
  bezeichnung: string;
  /** 12 (bis 2020) oder 13. Bei 12 fehlt dem Abschreibungs-Block die
   *  Umbuchungs-Spalte — die Abschreibungskette KANN dort nicht schließen,
   *  und das ist eine Eigenschaft der Vorlage, kein Fehler. */
  spalten: number;
  ahk_anfang: number; zugaenge: number; abgaenge: number;
  umbuchungen: number; ahk_ende: number;
  abschr_anfang: number; abschreibung: number; aufloesungen: number;
  zuschreibungen: number; abschr_umbuchungen: number; abschr_ende: number;
  buchwert: number; buchwert_vorjahr: number;
  proben: string[];
  herkunft_id: number | null;
};

/** Eine Untergruppe des Infrastrukturvermögens — Straßen, Brücken, Gleise.
 *  Aus einer ANDEREN Tabelle desselben Dokuments und erst ab 2022. */
export type VermoegensGruppe = {
  jahr: number;
  gruppe: string;
  buchwert: number;
  buchwert_vorjahr: number | null;
  herkunft_id: number | null;
};

export type Anlagen = {
  reihe: AnlagePosten[];
  jahre: number[];
  gruppen: VermoegensGruppe[];
  /** Die Jahre MIT Untergliederung — kürzer als `jahre`, und das muss die
   *  Seite sagen dürfen, statt eine Lücke als Null zu zeichnen. */
  gruppen_jahre: number[];
  proben: Record<string, string>;
};

/** Die Hauptposition „Sachvermögen" eines Jahres — oder null.
 *
 *  Nummer „2" ist die Zeile, um die es geht: Sie enthält Gebäude, Straßen und
 *  Fahrzeuge. Immaterielles (1) und Finanzvermögen (3) nutzen sich nicht ab. */
export function sachvermoegen(anlagen: Anlagen | undefined, jahr: number): AnlagePosten | null {
  return (anlagen?.reihe ?? []).find((z) => z.jahr === jahr && z.nr === "2") ?? null;
}

/** Das Infrastrukturvermögen (2.3) eines Jahres — Straßen, Brücken, Kanäle. */
export function infrastruktur(anlagen: Anlagen | undefined, jahr: number): AnlagePosten | null {
  return (anlagen?.reihe ?? []).find((z) => z.jahr === jahr && z.nr === "2.3") ?? null;
}

/** Baut die Stadt schneller auf, als ihr Bestand verfällt?
 *
 *  Gerechnet, nicht behauptet: Zugänge gegen Abschreibung derselben Zeile
 *  desselben Jahres. `null`, wo eine der beiden Zahlen fehlt — dann sagt die
 *  Seite nichts, statt eine Richtung zu raten. */
export function verzehr(posten: AnlagePosten | null): {
  zugaenge: number; abschreibung: number; saldo: number; faktor: number | null;
} | null {
  if (!posten) return null;
  const abschreibung = Math.abs(posten.abschreibung);
  if (!posten.zugaenge && !abschreibung) return null;
  return {
    zugaenge: posten.zugaenge,
    abschreibung,
    saldo: posten.zugaenge - abschreibung,
    faktor: posten.zugaenge > 0 ? abschreibung / posten.zugaenge : null,
  };
}

/** Die Straßen-Untergruppe eines Jahres, falls der Jahrgang sie führt. */
export function strassen(anlagen: Anlagen | undefined, jahr: number): VermoegensGruppe | null {
  return (anlagen?.gruppen ?? []).find(
    (g) => g.jahr === jahr && /Straßen/i.test(g.gruppe)) ?? null;
}

export function herkunftVon(daten: GebautDaten | null, id: number | null): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

export type Reihe = {
  schluessel: string;
  titel: string;
  jahre: GebautJahr[];
  /** Was in dieser Reihe fehlt — je Lücke das Jahr und die gemessene
   *  Differenz, soweit der Bestand eine führt. */
  fehlend: GebautLuecke[];
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
