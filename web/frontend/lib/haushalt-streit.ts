// Typen und Regeln für „Der Streit ums Geld" (/haushalt/streit).
//
// Die Seite zeigt drei Dinge je Haushaltsjahrgang: welche Änderungslisten zur
// Abstimmung standen, was in der Debatte gesagt wurde und wie am Ende
// abgestimmt wurde. Alles kommt aus `/council/haushalt/streit`, also aus den
// Ratsprotokollen — nicht aus einem Finanzdokument.
//
// AUSGEWOGENHEIT IST HIER KEINE GESCHMACKSFRAGE, SONDERN DIE HAUPTREGEL.
// Auf dieser Seite stehen Äußerungen von Personen, und jede Auswahl, die wir
// treffen, ist eine Aussage darüber, wer wichtig ist. Deshalb:
//
//  * **Die Reihenfolge ist die des Protokolls**, nie nach Länge, Fraktion oder
//    Größe sortiert. Wer zuerst sprach, steht zuerst.
//  * **Gekürzt wird nach einer Regel, die für alle gleich ist** — dieselbe
//    Zeichenzahl (`VORSCHAU_ZEICHEN`) für jede Rede, unabhängig davon, wer
//    sie gehalten hat. Der Rest steht eine Klick entfernt vollständig da.
//    Eine Kürzung „auf das Wesentliche" gäbe es hier nicht: Wer entscheidet,
//    was wesentlich ist, hat schon Politik gemacht.
//  * **Keine Vollständigkeits-Behauptung.** Es stehen ALLE Wortbeiträge da,
//    die im Protokollabschnitt des Haushalts-Sammelpunkts stehen — nicht alle,
//    die je zum Haushalt fielen.
//
// KEINE STIMMGRAFIKEN (Designsprache §7). Wie einzelne Ratsmitglieder
// abgestimmt haben, weiß das Ratsinformationssystem nicht; es kennt nur das
// Ergebnis je Abstimmung. Ein Balken „12 dafür, 8 dagegen" wäre erfunden.
// Deshalb steht das Ergebnis als Wort und Badge da, sonst nichts.

export type StreitRolle = "rat" | "verwaltung" | "leitung";

export type StreitWortbeitrag = {
  /** Anrede aus dem Protokoll — „Ratsherr", „Stadtkämmerin" … */
  anrede: string;
  /** Anzeigename: aus der Anwesenheitsliste, sonst wie im Protokoll. */
  name: string;
  /** Wortlaut des Protokolls, geglättet. Indirekte Rede — siehe `HINWEIS_REDE`. */
  text: string;
  /** Gruppen-bewusstes Label („FDP/Volt" bleibt die Gruppe), null bei Verwaltung/Leitung. */
  fraktion: string | null;
  /** Namensvettern im Rat: Fraktion nicht eindeutig bestimmbar. */
  fraktion_unklar: boolean;
  role: StreitRolle;
  zeichen: number;
};

export type StreitAntrag = {
  titel: string;
  outcome: string | null;
  vote: string | null;
  /** Fraktion(en) bzw. Gruppe hinter der Liste, null bei Verwaltungslisten. */
  author: string | null;
  ist_verwaltung: boolean;
  top: string | null;
  ksinr: number;
};

export type StreitBeschluss = {
  id: number;
  top: string | null;
  titel: string;
  outcome: string | null;
  vote: string | null;
  no_votes: number | null;
  abstentions: number | null;
  /** Der Abstimmungssatz, wie er im Protokoll steht. */
  wortlaut: string | null;
  template_number: string | null;
};

export type StreitStation = {
  ksinr: number;
  gremium: string;
  datum: string;
  top: string | null;
  official_text: StreitBeschluss | null;
  antraege: StreitAntrag[];
  debatte: StreitWortbeitrag[];
  protokoll_url: string | null;
};

export type StreitRunde = { year: number; stationen: StreitStation[] };
export type StreitDaten = { runden: StreitRunde[] };

/** So viele Zeichen jeder Rede stehen ohne Aufklappen da — für jede gleich. */
export const VORSCHAU_ZEICHEN = 320;

/** Ab dieser Länge lohnt das Aufklappen überhaupt. */
const KURZ_GENUG = VORSCHAU_ZEICHEN + 90;

export const HINWEIS_REDE =
  "Ratsprotokolle geben Reden in indirekter Rede wieder — es sind Zusammenfassungen " +
  "der Schriftführung, keine wörtlichen Zitate. Was hier steht, ist der Wortlaut des " +
  "Protokolls, nicht der Wortlaut der Rednerin oder des Redners.";

/** Vorschau + Rest einer Rede. Der Schnitt fällt auf die nächste Wortgrenze,
 *  damit kein Wort zerrissen wird; die Regel ist für jede Rede dieselbe. */
export function vorschau(text: string): { kopf: string; rest: string } {
  if (text.length <= KURZ_GENUG) return { kopf: text, rest: "" };
  const grenze = text.lastIndexOf(" ", VORSCHAU_ZEICHEN);
  const schnitt = grenze > VORSCHAU_ZEICHEN * 0.6 ? grenze : VORSCHAU_ZEICHEN;
  return { kopf: text.slice(0, schnitt).trimEnd(), rest: text.slice(schnitt).trimStart() };
}

/** Die Jahrgänge, neueste zuerst — so steht der aktuelle Streit oben. */
export function jahrgaenge(daten: StreitDaten | null): number[] {
  return (daten?.runden ?? []).map((r) => r.year).sort((a, b) => b - a);
}

export function runde(daten: StreitDaten | null, year: number | null): StreitRunde | null {
  if (!daten || year == null) return null;
  return daten.runden.find((r) => r.year === year) ?? null;
}

/** Die Station, an der die Debatte hängt: die mit den meisten Wortbeiträgen.
 *  Das ist in aller Regel der Rat — aber nicht per Gremiumsnamen gesucht,
 *  sondern am Inhalt, weil 2022 der Ausschuss ausführlicher protokolliert ist. */
export function debattenStation(r: StreitRunde | null): StreitStation | null {
  if (!r?.stationen.length) return null;
  return r.stationen.reduce((a, b) => (b.debatte.length > a.debatte.length ? b : a));
}

/** Stationen, an denen überhaupt über Änderungslisten abgestimmt wurde. */
export function antragsStationen(r: StreitRunde | null): StreitStation[] {
  return (r?.stationen ?? []).filter((s) => s.antraege.length > 0);
}

/** Die Schlussabstimmung über die Haushaltssatzung — die letzte Station, die
 *  eine trägt. Vorherige Stationen haben denselben Punkt vertagt. */
export function schlussbeschluss(r: StreitRunde | null): StreitStation | null {
  const mit = (r?.stationen ?? []).filter((s) => s.official_text?.outcome === "angenommen");
  return mit.length ? mit[mit.length - 1] : null;
}

/** Wie viele Reden je Fraktion — für die ehrliche Mengenangabe am Kicker.
 *  Verwaltung und Sitzungsleitung zählen getrennt, nicht zu einer Fraktion:
 *  Die Leitung ruft jeden Punkt auf und käme sonst auf ein Vielfaches. */
export function redenJeFraktion(station: StreitStation | null): { label: string; n: number }[] {
  const zaehler = new Map<string, number>();
  for (const b of station?.debatte ?? []) {
    if (b.role !== "rat") continue;
    const label = b.fraktion ?? "ohne eindeutige Fraktion";
    zaehler.set(label, (zaehler.get(label) ?? 0) + 1);
  }
  return [...zaehler].map(([label, n]) => ({ label, n })).sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
}

/** Label der Zeile für Listen ohne erkannte Fraktion im Titel — in der
 *  Praxis Änderungslisten einzelner Ratsmitglieder. Sie bleiben in der
 *  Bilanz sichtbar: Wer sie wegließe, zählte nur die Fraktionen. */
export const EINZELNE = "Einzelne Ratsmitglieder";

export type BilanzStand = { ein: number; durch: number };
export type BilanzZeile = { author: string; fa: BilanzStand; rat: BilanzStand };

/** Die Verhandlungsbilanz eines Jahrgangs für <PunkteBilanz> (GB-09):
 *  je Urheber, getrennt nach Finanzausschuss und Rat, wie viele
 *  Abstimmungen über Änderungslisten es gab (`ein`) und wie viele davon
 *  eine Mehrheit fanden (`durch`). Gezählt werden ABSTIMMUNGEN, keine
 *  Listen — dieselbe Liste kann an beiden Stationen aufgerufen werden.
 *
 *  `durch` zählt nur `angenommen`; alles andere (abgelehnt, vertagt, ohne
 *  protokolliertes Ergebnis) bleibt ein ungefüllter Punkt — die Legende der
 *  Grafik benennt das. Verwaltungslisten zählen nicht: Die Verwaltung
 *  schreibt ihren eigenen Entwurf fort, sie „gewinnt" keine Abstimmung.
 *  Keine Sortierung hier — die übernimmt <PunkteBilanz> selbst (alphabetisch,
 *  fest). */
export function verhandlungsBilanz(r: StreitRunde | null): BilanzZeile[] {
  const bilanz = new Map<string, BilanzZeile>();
  for (const s of r?.stationen ?? []) {
    // Die Stationen sind in Oldenburg der Ausschuss für Finanzen und
    // Beteiligungen und der Rat (council/store.haushalt_streit) — alles,
    // was nicht der Rat ist, zählt deshalb zur Ausschuss-Spalte.
    const page: keyof Omit<BilanzZeile, "author"> = s.gremium === "Rat" ? "rat" : "fa";
    for (const a of s.antraege) {
      if (a.ist_verwaltung) continue;
      const author = a.author ?? EINZELNE;
      const z = bilanz.get(author)
        ?? { author, fa: { ein: 0, durch: 0 }, rat: { ein: 0, durch: 0 } };
      z[page].ein += 1;
      if (a.outcome === "angenommen") z[page].durch += 1;
      bilanz.set(author, z);
    }
  }
  return [...bilanz.values()];
}

/** Wortbeiträge ohne Fraktionszuordnung — über ALLE Jahrgänge gezählt, denn
 *  die Aussage („n von m tragen keine Fraktion") beschreibt den Bestand,
 *  nicht ein Jahr. Verwaltung und Sitzungsleitung zählen zu `gesamt`, aber
 *  nie zu `ohne`: Sitzungsleitung ist eine Rolle, keine Fraktion. */
export function ohneZuordnung(daten: StreitDaten | null): { ohne: number; gesamt: number } {
  let ohne = 0, gesamt = 0;
  for (const r of daten?.runden ?? []) {
    for (const s of r.stationen) {
      for (const b of s.debatte) {
        gesamt += 1;
        if (b.role === "rat" && b.fraktion_unklar) ohne += 1;
      }
    }
  }
  return { ohne, gesamt };
}

/** Die ehrliche Mengenangabe der Quelle: wie viele Änderungslisten (alle,
 *  auch die der Verwaltung) und Wortbeiträge über welchen Zeitraum im
 *  Bestand stehen — gezählt, nicht geschrieben. */
export function balance(daten: StreitDaten | null): {
  listen: number; beitraege: number; jahrgaenge: number; von: number; bis: number;
} {
  const runden = daten?.runden ?? [];
  let listen = 0, beitraege = 0;
  for (const r of runden) {
    for (const s of r.stationen) {
      listen += s.antraege.length;
      beitraege += s.debatte.length;
    }
  }
  const years = runden.map((r) => r.year);
  return {
    listen, beitraege, jahrgaenge: runden.length,
    von: years.length ? Math.min(...years) : 0,
    bis: years.length ? Math.max(...years) : 0,
  };
}

export function datumLang(iso: string): string {
  const [j, m, t] = iso.split("-").map(Number);
  if (!j || !m || !t) return iso;
  return new Date(Date.UTC(j, m - 1, t)).toLocaleDateString("de-DE", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}

/** Kurzform eines Gremiumsnamens für Kicker-Zeilen. */
export function gremiumKurz(name: string): string {
  return name.replace("Ausschuss für Finanzen und Beteiligungen", "Finanzausschuss");
}
