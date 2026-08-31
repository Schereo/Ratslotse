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
export type Art = { field: string; titel: string; amount: number };

export type GebautJahr = {
  year: number;
  /** `"kameral"` (bis 2009) oder `"doppik"` (ab 2010). */
  accounting_system: string;
  /** Die ausgewiesene Summenspalte in Euro. */
  total: number;
  arten: Art[];
  herkunft_id: number | null;
};

/** Ein Jahr, das die Reihe ankündigt und nicht belegt.
 *
 *  `difference` ist die GEMESSENE Lücke in Euro (Auszahlungsarten minus
 *  ausgewiesene Summe, vorzeichenbehaftet) — sie kommt aus dem Ingest-Lauf,
 *  der den Jahrgang verworfen hat, und steht nirgends im Frontend. `null`,
 *  wo der Bestand keine Messung führt; dann nennt die Seite die Lücke ohne
 *  Betrag, statt einen zu erfinden. */
export type GebautLuecke = { year: number; difference: number | null };

export type GebautDaten = {
  series: GebautJahr[];
  years: number[];
  /** Was diese Zahlen zählen — kommt aus `council/investitionen_ist.py`,
   *  damit Oberfläche und Datenbank dieselbe Auskunft geben. */
  abgrenzung: string;
  accounting_systems: { key: string; titel: string }[];
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
 *  Die Vorzeichen sind die des Dokuments: `disposals`, `depreciation` und
 *  `depreciation_closing` stehen negativ. Wer sie beim Anzeigen dreht, muss es überall
 *  tun — eine halb gedrehte Reihe ist schlimmer als eine ungedrehte. */
export type AnlagePosten = {
  year: number;
  /** Gliederung wie im Dokument: „1", „1.1", „2", „2.3" … */
  nr: string;
  label: string;
  /** 12 (bis 2020) oder 13. Bei 12 fehlt dem Abschreibungs-Block die
   *  Umbuchungs-Spalte — die Abschreibungskette KANN dort nicht schließen,
   *  und das ist eine Eigenschaft der Vorlage, kein Fehler. */
  spalten: number;
  cost_opening: number; additions: number; disposals: number;
  transfers: number; cost_closing: number;
  depreciation_opening: number; depreciation: number; depreciation_releases: number;
  write_ups: number; depreciation_transfers: number; depreciation_closing: number;
  book_value: number; book_value_prior_year: number;
  probes: string[];
  herkunft_id: number | null;
};

/** Eine Untergruppe des Infrastrukturvermögens — Straßen, Brücken, Gleise.
 *  Aus einer ANDEREN Tabelle desselben Dokuments und erst ab 2022. */
export type VermoegensGruppe = {
  year: number;
  gruppe: string;
  book_value: number;
  book_value_prior_year: number | null;
  herkunft_id: number | null;
};

export type Anlagen = {
  series: AnlagePosten[];
  years: number[];
  gruppen: VermoegensGruppe[];
  /** Die Jahre MIT Untergliederung — kürzer als `years`, und das muss die
   *  Seite sagen dürfen, statt eine Lücke als Null zu zeichnen. */
  gruppen_jahre: number[];
  probes: Record<string, string>;
};

/** Die Hauptposition „Sachvermögen" eines Jahres — oder null.
 *
 *  Nummer „2" ist die Zeile, um die es geht: Sie enthält Gebäude, Straßen und
 *  Fahrzeuge. Immaterielles (1) und Finanzvermögen (3) nutzen sich nicht ab. */
export function sachvermoegen(anlagen: Anlagen | undefined, year: number): AnlagePosten | null {
  return (anlagen?.series ?? []).find((z) => z.year === year && z.nr === "2") ?? null;
}

/** Das Infrastrukturvermögen (2.3) eines Jahres — Straßen, Brücken, Kanäle. */
export function infrastruktur(anlagen: Anlagen | undefined, year: number): AnlagePosten | null {
  return (anlagen?.series ?? []).find((z) => z.year === year && z.nr === "2.3") ?? null;
}

/** Baut die Stadt schneller auf, als ihr Bestand verfällt?
 *
 *  Gerechnet, nicht behauptet: Zugänge gegen Abschreibung derselben Zeile
 *  desselben Jahres. `null`, wo eine der beiden Zahlen fehlt — dann sagt die
 *  Seite nichts, statt eine Richtung zu raten. */
export function verzehr(posten: AnlagePosten | null): {
  additions: number; depreciation: number; balance: number; faktor: number | null;
} | null {
  if (!posten) return null;
  const depreciation = Math.abs(posten.depreciation);
  if (!posten.additions && !depreciation) return null;
  return {
    additions: posten.additions,
    depreciation,
    balance: posten.additions - depreciation,
    faktor: posten.additions > 0 ? depreciation / posten.additions : null,
  };
}

/** Die Straßen-Untergruppe eines Jahres, falls der Jahrgang sie führt. */
export function strassen(anlagen: Anlagen | undefined, year: number): VermoegensGruppe | null {
  return (anlagen?.gruppen ?? []).find(
    (g) => g.year === year && /Straßen/i.test(g.gruppe)) ?? null;
}

export function herkunftVon(daten: GebautDaten | null, id: number | null): Herkunft | null {
  if (!daten || id == null) return null;
  return daten.herkunft[String(id)] ?? null;
}

export type Reihe = {
  key: string;
  titel: string;
  years: GebautJahr[];
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
  return daten.accounting_systems
    .map((r) => ({
      key: r.key,
      titel: r.titel,
      years: daten.series.filter((z) => z.accounting_system === r.key),
      fehlend: daten.fehlend[r.key] ?? [],
    }))
    .filter((r) => r.years.length > 0);
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
    (b.years[b.years.length - 1].year > a.years[a.years.length - 1].year ? b : a));
}

/** Der größte Posten eines Jahrgangs — gerechnet, nicht beschriftet.
 *
 *  Eine Seite, die „die meisten Mittel gehen in Baumaßnahmen" als Text trägt,
 *  wird mit dem nächsten Jahrgang still falsch: 2025 ist es „Sonstige
 *  Investitionstätigkeit", 2016 war es „bewegliches Sachvermögen". */
export function groessterPosten(z: GebautJahr | null): Art | null {
  if (!z || !z.arten.length) return null;
  return z.arten.reduce((a, b) => (b.amount > a.amount ? b : a));
}

/** Alle Auszahlungsarten einer Reihe, in der Spaltenfolge der Quelle — die
 *  Legende einer Reihe.
 *
 *  Aus den Daten und nicht aus einer Konstante: Käme eine Art dazu oder fiele
 *  eine weg, stünde die Legende sonst gegen die Balken. */
export function artenDerReihe(r: Reihe | null): { field: string; titel: string }[] {
  if (!r) return [];
  const gesehen = new Map<string, string>();
  for (const z of r.years) {
    for (const a of z.arten) if (!gesehen.has(a.field)) gesehen.set(a.field, a.titel);
  }
  return [...gesehen].map(([field, titel]) => ({ field, titel }));
}

/** Deutsche Anzeige eines Euro-Betrags in Millionen, eine Nachkommastelle. */
export function deMioEuro(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return (v / 1e6).toLocaleString("de-DE",
    { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}
