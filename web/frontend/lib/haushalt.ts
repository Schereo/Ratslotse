// Datenschicht des Haushalts-Bereichs (Design-Serie „Haushalt" H-01…H-09).
// Quelle ist GET /api/council/haushalt: Ergebnishaushalt je Planjahr
// (Teilhaushalte + Summenzeile), dazu Ist-Steuereinnahmen und Steuerkraft —
// hier stehen nur Ableitungen, keine erfundenen Zahlen (Designprinzip:
// fehlende Daten heißen sichtbar „[folgt]", nie interpoliert).

export type HaushaltZeile = {
  bereich: string;
  ertraege: number | null;
  aufwendungen: number | null;
  ergebnis: number | null;
  is_summe: 0 | 1;
  source_url: string | null;
};

/** Ein Posten der Ergebnisrechnung aus dem Jahresabschluss (#500):
 *  `ansatz` = was geplant war, `ergebnis` = was es tatsächlich wurde. */
export type ErgebnisPosten = {
  jahr: number; nr: number; bezeichnung: string;
  /** null = Kernverwaltung gesamt, sonst der Teilhaushalt (1–13). */
  thh_nr: number | null; thh_name: string | null;
  vorjahr: number | null; ansatz: number | null;
  ergebnis: number | null; abweichung: number | null;
  ist_summe: 0 | 1;
  quelle_label: string | null; quelle_url: string | null;
};

/** Produktebene aus den Teilhaushalts-Plänen (#500) — was einzelne Aufgaben
 *  kosten. `ergebnis` ist negativ = Zuschussbedarf. */
export type Produkt = {
  jahr: number; produkt_nr: string; produkt_name: string;
  thh_nr: number | null; thh_name: string | null; amt: string | null;
  ertraege: number | null; aufwendungen: number | null; ergebnis: number | null;
  quelle_label: string | null; quelle_url: string | null;
};

export type ProdukteAntwort = {
  jahr: number; produkte: Produkt[];
  abdeckung_prozent: number | null; plan_aufwendungen: number | null;
};

export type HaushaltDaten = {
  jahre: Record<string, HaushaltZeile[]>;
  steuern: { jahr: number; art: string; betrag: number | null }[];
  steuerkraft: {
    jahr: number; messzahl: number | null; messzahl_je_ew: number | null;
    zuweisungen: number | null; zuweisungen_je_ew: number | null;
  }[];
  /** Jüngste Einwohnerzahl — Bezugsgröße für Pro-Kopf-Einordnungen. */
  einwohner: { jahr: number; einwohner: number } | null;
  /** Ansatz und Ergebnis je Posten aus den Jahresabschlüssen. */
  ergebnisrechnung?: ErgebnisPosten[];
  /** Jahre, für die die Produktebene vorliegt. */
  produkt_jahre?: number[];
  /** Jahre mit „geplant gegen tatsächlich" je Teilhaushalt. */
  plan_ist_jahre?: number[];
};

/** „Geplant gegen tatsächlich" je abgeschlossenem Jahr, in Mio.
 *
 *  Verglichen wird das **Jahresergebnis**: ordentliches (Posten 21) plus
 *  außerordentliches Ergebnis (24). Nur das ordentliche zu nehmen schmeichelte
 *  der Stadt — die außerordentlichen Posten waren zuletzt durchweg negativ.
 *  Jahre, in denen ein Posten fehlt, fallen raus statt halb gerechnet zu
 *  werden. */
export function planGegenIst(
  daten: HaushaltDaten,
): { jahr: number; plan: number; ist: number; delta: number }[] {
  const posten = daten.ergebnisrechnung ?? [];
  const jahre = [...new Set(posten.map((p) => p.jahr))].sort((a, b) => a - b);
  return jahre
    .map((jahr) => {
      const teile = [21, 24].map((nr) => posten.find((p) => p.jahr === jahr && p.nr === nr));
      if (teile.some((t) => !t || t.ansatz == null || t.ergebnis == null)) return null;
      const plan = teile.reduce((s, t) => s + (t!.ansatz as number), 0) / 1e6;
      const ist = teile.reduce((s, t) => s + (t!.ergebnis as number), 0) / 1e6;
      return {
        jahr,
        plan: Math.round(plan * 10) / 10,
        ist: Math.round(ist * 10) / 10,
        delta: Math.round((ist - plan) * 10) / 10,
      };
    })
    .filter((x): x is { jahr: number; plan: number; ist: number; delta: number } => x !== null);
}

// --- Flussbild: Herkunft → ein Topf → Verwendung (Design H-18) -------------
//
// Kein klassisches Sankey. Ein durchgehendes Band von „Gewerbesteuer" nach
// „Soziales" behauptete eine Zweckbindung, die der kommunale Haushalt nicht
// kennt: Alle Einnahmen finanzieren gemeinsam alle Ausgaben. Deshalb laufen
// hier ALLE Bänder in EINEN Knoten und von dort neu heraus — dass alles durch
// einen Topf läuft, ist die Aussage des Bildes.

/** Kurznamen der Ertragsarten für die Grafik — redaktionell, nah am amtlichen
 *  Begriff und ohne Deutung. Die Langfassung steht in der Tabelle und im
 *  aria-Label; wo kein Kurzname gepflegt ist, gilt die Langfassung. */
export const ERTRAGSART_KURZ: Record<number, string> = {
  1: "Steuern",
  2: "Zuwendungen und Umlagen",
  3: "Auflösung von Sonderposten",
  4: "Transfererträge",
  5: "Gebühren und Beiträge",
  6: "privatrechtliche Entgelte",
  7: "Kostenerstattungen",
  8: "Zinsen",
  9: "Eigenleistungen",
  10: "Bestandsveränderungen",
  11: "sonstige Erträge",
};

export type FlussBand = {
  id: string;
  /** Kurzform für die Grafik. */
  label: string;
  /** Amtliche Bezeichnung — Tabelle, Titel, aria. */
  lang: string;
  /** Betrag in EURO (nicht Mio.): Sämtliche Summen und die Probe rechnen mit
   *  Rohwerten, sonst driftet der Vergleich um bis zu 0,1 je Posten. */
  wert: number;
  art: "posten" | "rest" | "ausgleich";
};

export type FlussSeite = {
  /** Absteigend nach Betrag; „rest" und „ausgleich" stehen immer hinten. */
  baender: FlussBand[];
  /** Die ausgewiesene Summenzeile (Posten 12 bzw. 20) in Euro. */
  gesamt: number;
  /** Summe der Einzelposten in Euro — ohne rest/ausgleich. */
  teile: number;
};

export type FlussDaten = {
  jahr: number;
  stand: "plan" | "ist";
  herkunft: FlussSeite;
  verwendung: FlussSeite;
  /** Gemeinsame Achse beider Seiten in Euro — die größere der beiden Summen. */
  skala: number;
  /** Erträge − Aufwendungen in Euro. */
  saldo: number;
  /** Summenprobe (Geometrie): Σ der gezeichneten Bänder je Seite. */
  summeLinks: number;
  summeRechts: number;
  /** Beide Seiten ergeben dieselbe Skala — die Bandbreiten sind vergleichbar. */
  stimmt: boolean;
  /** Beide Seiten sind bis auf ≤ 2 % durch Einzelposten gedeckt. Sonst wird
   *  das Bild NICHT gezeichnet: eine gestreckte Grafik wäre eine Behauptung. */
  aufgeschluesselt: boolean;
};

/** 0,05 Mio. € — feiner als die Anzeige (eine Nachkommastelle in Mio.). */
const FLUSS_TOLERANZ = 50_000;

/** Jahre, für die sich ein Flussbild bauen lässt: Der Jahresabschluss muss
 *  Ertragsarten UND Teilhaushalte hergeben. Ein Abschluss ohne
 *  Teilhaushalts-Ebene (2019) trägt nur die halbe Grafik — die zeigen wir
 *  nicht, sonst stünde rechts nichts neben einer vollen linken Seite. */
export function flussJahre(daten: HaushaltDaten): number[] {
  const posten = daten.ergebnisrechnung ?? [];
  return [...new Set(posten.map((p) => p.jahr))]
    .sort((a, b) => a - b)
    .filter((jahr) => {
      const gesamt = posten.filter((p) => p.jahr === jahr && p.thh_nr == null);
      return (
        gesamt.some((p) => p.nr >= 1 && p.nr <= 11) &&
        gesamt.some((p) => p.nr === 12) &&
        gesamt.some((p) => p.nr === 20) &&
        posten.some((p) => p.jahr === jahr && p.thh_nr != null && p.nr === 20)
      );
    });
}

/** Eine Seite bauen: Einzelposten, dann die beiden Ehrlichkeits-Bänder.
 *
 *  `rest` = was die Summenzeile mehr ausweist, als die Einzelposten hergeben
 *  (bei uns unlesbare Zeilen) — sichtbar als eigenes Band statt still verteilt.
 *  `ausgleich` = der Abstand zur gemeinsamen Skala, also genau der Saldo: Bei
 *  einem Minus steht links „aus dem Ersparten", bei einem Plus rechts
 *  „bleibt übrig". Erst dadurch sind beide Seiten wirklich gleich lang — und
 *  das Bild behauptet nicht, ein Defizit-Haushalt sei ausgeglichen. */
function flussSeite(
  teile: FlussBand[], gesamt: number, skala: number,
  restLabel: string, ausgleichLabel: string,
): FlussSeite {
  const summeTeile = teile.reduce((s, b) => s + b.wert, 0);
  const baender = [...teile].sort((a, b) => b.wert - a.wert);
  const rest = gesamt - summeTeile;
  if (rest > FLUSS_TOLERANZ) {
    baender.push({ id: "rest", label: restLabel, lang: restLabel, wert: rest, art: "rest" });
  }
  const gedeckt = summeTeile + Math.max(rest, 0);
  const ausgleich = skala - gedeckt;
  if (ausgleich > FLUSS_TOLERANZ) {
    baender.push({
      id: "ausgleich", label: ausgleichLabel, lang: ausgleichLabel,
      wert: ausgleich, art: "ausgleich",
    });
  }
  return { baender, gesamt, teile: summeTeile };
}

/** Das Flussbild eines Jahres in einem Stand (Plan oder Ist).
 *
 *  Links die Ertragsarten (Posten 01–11), rechts die Teilhaushalte (Posten 20
 *  je `thh_nr`) — beide aus derselben Tabelle desselben Jahres, damit nie zwei
 *  Stände nebeneinander stehen. `null`, wenn eine Seite fehlt. */
export function flussbild(
  daten: HaushaltDaten, jahr: number, stand: "plan" | "ist",
): FlussDaten | null {
  const zahl = (p: ErgebnisPosten | undefined) =>
    p ? (stand === "ist" ? p.ergebnis : p.ansatz) : null;
  const rows = (daten.ergebnisrechnung ?? []).filter((p) => p.jahr === jahr);
  const gesamt = rows.filter((p) => p.thh_nr == null);

  const ertraege = zahl(gesamt.find((p) => p.nr === 12));
  const aufwendungen = zahl(gesamt.find((p) => p.nr === 20));
  if (!ertraege || !aufwendungen || ertraege <= 0 || aufwendungen <= 0) return null;

  const arten: FlussBand[] = gesamt
    .filter((p) => p.nr >= 1 && p.nr <= 11 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `art-${p.nr}`,
      label: ERTRAGSART_KURZ[p.nr] ?? p.bezeichnung,
      lang: p.bezeichnung,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  const bereiche: FlussBand[] = rows
    .filter((p) => p.thh_nr != null && p.nr === 20 && (zahl(p) ?? 0) > 0)
    .map((p) => ({
      id: `thh-${p.thh_nr}`,
      label: p.thh_name ?? `Teilhaushalt ${p.thh_nr}`,
      lang: p.thh_name ?? `Teilhaushalt ${p.thh_nr}`,
      wert: zahl(p) as number,
      art: "posten" as const,
    }));
  if (!arten.length || !bereiche.length) return null;

  // Die Skala deckt auch den Fall ab, dass Einzelposten ihre eigene
  // Summenzeile übersteigen (fehlgelesene Zeile): Dann ragt nichts über den
  // Knoten hinaus, und `aufgeschluesselt` schaltet das Bild ohnehin ab.
  const skala = Math.max(
    ertraege, aufwendungen,
    arten.reduce((s, b) => s + b.wert, 0),
    bereiche.reduce((s, b) => s + b.wert, 0),
  );

  const herkunft = flussSeite(arten, ertraege, skala,
    "im Abschluss nicht aufgeschlüsselt", "aus dem Ersparten");
  const verwendung = flussSeite(bereiche, aufwendungen, skala,
    "im Abschluss nicht aufgeschlüsselt", "bleibt übrig");

  const summeLinks = herkunft.baender.reduce((s, b) => s + b.wert, 0);
  const summeRechts = verwendung.baender.reduce((s, b) => s + b.wert, 0);
  const luecke = (s: FlussSeite) => Math.abs(s.gesamt - s.teile);
  return {
    jahr, stand, herkunft, verwendung, skala,
    saldo: ertraege - aufwendungen,
    summeLinks, summeRechts,
    stimmt: Math.abs(summeLinks - summeRechts) <= FLUSS_TOLERANZ
      && Math.abs(summeLinks - skala) <= FLUSS_TOLERANZ,
    aufgeschluesselt: luecke(herkunft) <= 0.02 * herkunft.gesamt
      && luecke(verwendung) <= 0.02 * verwendung.gesamt,
  };
}

/** Kleine Posten bündeln, damit die Bänder beschriftbar bleiben: Wer unter
 *  `mindestAnteil` der Skala liegt, wandert in einen Sammelposten „weitere".
 *
 *  Die Schwelle ist eine Lesbarkeits-, keine Relevanzentscheidung — ein Band
 *  unter der Zeilenhöhe seiner eigenen Beschriftung ist nicht mehr zuzuordnen.
 *  Was im Sammelposten steckt, steht aufklappbar darunter und vollständig in
 *  der Tabelle. Die Ehrlichkeits-Bänder (rest/ausgleich) werden nie gebündelt:
 *  Genau sie erklären, warum das Bild aussieht, wie es aussieht. */
export function fasseKleineZusammen(
  baender: FlussBand[], skala: number, mindestAnteil: number,
): { gezeigt: FlussBand[]; gebuendelt: FlussBand[] } {
  const gross = baender.filter(
    (b) => b.art !== "posten" || b.wert >= mindestAnteil * skala);
  const gebuendelt = baender.filter(
    (b) => b.art === "posten" && b.wert < mindestAnteil * skala);
  if (gebuendelt.length < 2) return { gezeigt: baender, gebuendelt: [] };
  const sammel: FlussBand = {
    id: "weitere",
    label: `${gebuendelt.length} weitere`,
    lang: `${gebuendelt.length} weitere Posten`,
    wert: gebuendelt.reduce((s, b) => s + b.wert, 0),
    art: "posten",
  };
  // Sammelposten und Ehrlichkeits-Bänder ans Ende: Der Stapel liest sich von
  // oben nach unten „groß nach klein", die Sonderfälle stehen unten.
  const posten = gross.filter((b) => b.art === "posten");
  const sonder = gross.filter((b) => b.art !== "posten");
  return { gezeigt: [...posten, sammel, ...sonder], gebuendelt };
}

/** Das Produkt, dessen Zuschussbedarf einem Betrag am nächsten kommt — die
 *  Übersetzung von „4,0 Mio." in etwas, das man kennt.
 *
 *  `thhName` grenzt bewusst auf denselben Teilhaushalt ein: Eine Kürzung bei
 *  Kultur mit einer Sozialleistung zu vergleichen legt nahe, man könne die
 *  stattdessen streichen. Wo für den Bereich keine Produkte vorliegen, gibt es
 *  lieber keinen Vergleich als einen schiefen. */
export function naechstesProdukt(
  produkte: Produkt[], mioBetrag: number, thhName?: string,
): Produkt | null {
  if (mioBetrag < 0.2) return null;
  const passend = produkte.filter((p) =>
    p.ergebnis != null && p.ergebnis < 0 && (!thhName || p.thh_name === thhName));
  if (!passend.length) return null;
  return passend.reduce((best, p) =>
    Math.abs(-(p.ergebnis as number) / 1e6 - mioBetrag)
      < Math.abs(-(best.ergebnis as number) / 1e6 - mioBetrag) ? p : best);
}

/** Redaktionell gepflegte Konstanten — NICHT aus der DB. Quelle: Genehmigung
 *  des Haushalts 2026 durch das Nds. Innenministerium (04/2026), oldenburg.de.
 *  Beim nächsten Haushaltsjahr prüfen und nachziehen. */
export const RUECKLAGE_MIO = 195;
export const RUECKLAGE_STAND = "Stand: Genehmigung Haushalt 2026 (04/2026)";

export function mio(euro: number | null | undefined): number | null {
  if (euro == null) return null;
  return Math.round(euro / 100_000) / 10; // eine Nachkommastelle, in Mio.
}

/** Deutsche Anzeige „283,1" — Zahlen kommen bereits als Mio.-Wert. */
export function deMio(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function jahreSortiert(daten: HaushaltDaten): number[] {
  return Object.keys(daten.jahre).map(Number).sort((a, b) => a - b);
}

/** Lücken zwischen erstem und letztem vorhandenen Jahr — die Zeitreihe zeigt
 *  sie als schraffierte Kästen (Lücken-Konvention H-07), nie interpoliert. */
export function fehlendeJahre(vorhanden: number[]): number[] {
  if (vorhanden.length < 2) return [];
  const out: number[] = [];
  for (let y = vorhanden[0]; y <= vorhanden[vorhanden.length - 1]; y++) {
    if (!vorhanden.includes(y)) out.push(y);
  }
  return out;
}

export function summe(zeilen: HaushaltZeile[]): HaushaltZeile | undefined {
  return zeilen.find((z) => z.is_summe === 1);
}

export function bereiche(zeilen: HaushaltZeile[]): HaushaltZeile[] {
  return zeilen.filter((z) => z.is_summe !== 1);
}

/** Kostendeckungsgrad in Prozent (eigene Erträge / Aufwendungen), 0–100. */
export function deckung(z: HaushaltZeile): number | null {
  if (!z.aufwendungen || z.aufwendungen <= 0 || z.ertraege == null) return null;
  return Math.round((z.ertraege / z.aufwendungen) * 100);
}

/** URL-Slug eines Bereichsnamens („Jugend und Familie" → jugend-und-familie). */
export function bereichSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Zeitreihe eines Bereichs über alle Jahre — nur exakt namensgleiche Zeilen.
 *  Die Teilhaushalts-Zuschnitte ändern sich über die Jahre; eine kurze Reihe
 *  ist dann die ehrliche Antwort, keine fehlende. */
export function bereichsReihe(
  daten: HaushaltDaten, name: string,
): { jahr: number; zeile: HaushaltZeile }[] {
  return jahreSortiert(daten)
    .map((jahr) => {
      const z = daten.jahre[String(jahr)]?.find((r) => r.bereich === name);
      return z ? { jahr, zeile: z } : null;
    })
    .filter((x): x is { jahr: number; zeile: HaushaltZeile } => x !== null);
}

/** Quelle einer Jahres-Scheibe menschenlesbar (PDF vs. Open-Data-CSV). */
export function quellenLabel(zeilen: HaushaltZeile[], jahr: number): { text: string; url: string | null } {
  const url = zeilen[0]?.source_url ?? null;
  const csv = url?.includes("opendata.oldenburg.de");
  return {
    text: csv
      ? `Haushaltsplan ${jahr}, Stadt Oldenburg — Open-Data-Portal (CSV, Lizenz dl-de/by-2.0)`
      : `Beschlossener Haushaltsplan ${jahr}, Stadt Oldenburg (PDF)`,
    url,
  };
}

/** Kuratierte Kurzbeschreibungen der Teilhaushalte — redaktionell, nach dem
 *  Vorbericht des Haushaltsplans (Spiegel zu council/haushalt.py); bei neuen
 *  Jahrgängen prüfen. Bereiche ohne Eintrag zeigen den Block nicht. */
export const BEREICH_INFO: Record<string, string> = {
  "Jugend und Familie":
    "Der größte Brocken sind die Kindertagesstätten — die Stadt betreibt eigene, " +
    "bezuschusst freie Träger und zahlt für Plätze in der Kindertagespflege. Dazu " +
    "kommt die Jugendhilfe: Hilfen zur Erziehung, Pflegefamilien, Heimunterbringung, " +
    "Jugendarbeit und der Allgemeine Soziale Dienst. Vieles davon ist gesetzliche " +
    "Pflicht — wie gut es ausgestattet ist, entscheidet der Rat.",
  "Soziales und Gesundheit":
    "Vor allem gesetzliche Sozialleistungen, Hilfen zur Pflege und der öffentliche " +
    "Gesundheitsdienst. Ein großer Teil der Ausgaben wird durch Erstattungen von " +
    "Bund und Land gedeckt — deshalb ist der Bereich brutto der größte, unterm " +
    "Strich aber nicht der teuerste.",
  "Schule und Bildung":
    "Schulgebäude, Ausstattung und Ganztagsangebote der Stadt als Schulträgerin — " +
    "die Lehrkräfte selbst bezahlt das Land.",
  "Finanzmanagement und Recht":
    "Die zentrale Finanzwirtschaft: Hier werden Steuern und Zuweisungen für die " +
    "ganze Stadt verbucht. Die hohen Einnahmen sind kein Gewinn der Kämmerei — " +
    "sie werden von hier auf alle Aufgaben verteilt.",
  "Kultur, Museen, Sport":
    "Museen, Bibliotheken sowie Kultur- und Sportförderung — überwiegend " +
    "freiwillige Leistungen, über deren Umfang der Rat frei entscheidet.",
  "Verkehr und Straßenbau": "Straßen, Radwege, Brücken und der Nahverkehr.",
  "Sicherheit und Ordnung": "Feuerwehr, Rettungsdienst und Ordnungsverwaltung.",
  Stadtplanung: "Bauleitplanung und Stadtentwicklung.",
};
