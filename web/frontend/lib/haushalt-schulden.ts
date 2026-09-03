// Schuldenzeitreihe (/haushalt/schulden) — Typen und Rechenwege.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type SchuldenJahr = {
  year: number;
  /** Die vier Schuldenarten in Euro. `null`, wo die Aufteilung an ihrer Probe
   *  gescheitert ist — dann steht in `breakdown_rejected`, wie groß die
   *  Lücke war. Die Summe daneben bleibt trotzdem gültig. */
  credit_market: number | null;
  special_funds: number | null;
  public_authorities: number | null;
  municipal_enterprises: number | null;
  total: number;
  /** Betrag je Einwohner*in — die Angabe DER QUELLE, nicht unsere Division. */
  per_capita: number | null;
  breakdown_rejected: number | null;
  /** Die Quelle hat diesen Jahrgang nachträglich korrigiert („r"). */
  revised: number;
  herkunft_id: number | null;
};

/** Ein Ratsbeschluss zu einer Bürgschaft. */
export type BuergschaftsVorlage = {
  template_number: string;
  title: string;
  document_url: string | null;
  /** Datum der jüngsten Beratung; `null`, solange keine Sitzung verknüpft ist. */
  date: string | null;
  /** Zeigt auf die vorhandene Beschluss-Seite. */
  decision_id: number | null;
};

export type SchuldenDaten = {
  series: SchuldenJahr[];
  years: number[];
  /** Was diese Zahlen zählen — kommt aus `council/schulden.py`, damit
   *  Oberfläche und Datenbank dieselbe Auskunft geben. */
  scope_note: string;
  column_kinds: { field: string; title: string }[];
  /** Was der Schuldenstand im Jahr kostet: Posten 17 der Ergebnisrechnung
   *  („Zinsen und ähnliche Aufwendungen"), also Ist aus dem Jahresabschluss —
   *  nicht aus dem Jahrbuch, aus dem der Bestand kommt.
   *
   *  Ohne die Tilgung: Sie steht im Finanzhaushalt, mindert den Schuldenstand
   *  und ist kein Aufwand. Beides zusammenzuzählen ergäbe eine Zahl, die in
   *  keinem Dokument steht.
   *
   *  Leer, solange kein Jahresabschluss eingelesen ist. */
  interest_expense: { year: number; expense: number; herkunft_id: number | null }[];
  /** Wofür die Stadt geradesteht — die zweite, größere Zahl dieser Seite.
   *
   *  Sie ist **keine Schuld**: eine Bürgschaft wird nur fällig, wenn die
   *  verbürgte Gesellschaft nicht zahlt. Deshalb reisen drei Zahlen
   *  zusammen, und keine darf allein stehen — das Volumen (2024: 220,3 Mio.),
   *  die eigenen Geldschulden daneben (43,7 Mio.) und die Rückstellung für
   *  den erwarteten Ausfall (1,3 Mio.). */
  guarantees?: {
    series: Buergschaft[];
    /** Bilanzposten 3.7 je Jahr — nur 2021–2024 im Bestand; die früheren
     *  Abschlüsse gliedern die Rückstellungen anders. */
    provision: { year: number; value: number | null; herkunft_id: number | null }[];
    financial_debt: { year: number; value: number | null; herkunft_id: number | null }[];
    scope_note: string;
    /** Die Ratsbeschlüsse hinter dem Bestand — die GESCHICHTE, nicht die Summe.
     *
     *  Diese Beträge dürfen **nie addiert** werden, und die Liste zeigt selbst
     *  warum: „Verlängerung Ausfallbürgschaft … über 300.000 Euro für die
     *  Volkshochschule" ist dieselbe Bürgschaft wie zwei Jahre zuvor,
     *  „Anpassung … Weser-Ems Halle" ändert eine bestehende. Was der Bestand
     *  ist, sagt allein der Jahresabschluss (`series`). */
    templates?: BuergschaftsVorlage[];
  };
  /** Die dritte Schuldenzahl — was der ganze „Konzern Stadt" anteilig
   *  schuldet. `null`, solange der Tabellenband nicht eingelesen ist.
   *
   *  **Nur ein Stichtag, nie eine Kurve.** Der Berichtskreis wechselt zwischen
   *  den Ausgaben; die Quelle rät selbst davon ab, Jahrgänge zu vergleichen.
   *  `share_below_50` kommt gerechnet aus dem Backend und ist keine
   *  Nebensache: Er sagt, welcher Teil der Summe aus Unternehmen stammt, für
   *  die die Stadt nicht haftet (2024: 58 %). */
  integrated_debt?: {
    as_of_date: {
      year: number; total: number; per_capita: number | null;
      core_budget: number | null; extra_budgets: number | null;
      other: number | null; population: number | null;
      change: number | null; herkunft_id: number | null;
    };
    share_below_50: number | null;
    scope_note: string;
    no_series_note: string;
  } | null;
  provenance: Record<string, Herkunft>;
};

/** Ein Jahr Bürgschaftsbestand — mit zwei Angaben über seinen Beleg.
 *
 *  `exact` unterscheidet die beiden Darreichungsformen der Quelle: 2019/2020
 *  stehen auf den Cent in einer Tabelle, ab 2022 nennt der Anhang nur noch
 *  gerundete Millionen. `out_next_year` trifft genau ein Jahr — 2021 nennt
 *  seinen eigenen Bestand nicht, die Zahl steht nur im Abschluss von 2022.
 *  Beides gehört an die Anzeige, sonst sehen sechs verschieden belegte
 *  Jahrgänge gleich aus. */
export type Buergschaft = {
  year: number;
  balance: number;
  exact: boolean;
  out_next_year: boolean;
  source: string;
  /** Die Begründung im Wortlaut der Stadt, wo das Dokument eine nennt. */
  reason: string | null;
  /** Die im Grund genannte Einzelzahl — 2022 die 135,9 Mio. fürs Klinikum. */
  single_amount: number | null;
  probes: string[];
  herkunft_id: number | null;
};

/** Die Zinslast des jüngsten Jahres, für das sie vorliegt — oder null.
 *
 *  Bewusst nicht „das jüngste Schuldenjahr": Der Bestand reicht bis 2025, die
 *  Jahresabschlüsse enden früher. Wer beide Reihen am selben Jahr aufhängt,
 *  zeigt für die Zinsen dauerhaft nichts. */
export function juengsteZinslast(daten: SchuldenDaten | null) {
  const series = daten?.interest_expense ?? [];
  return series.length ? series[series.length - 1] : null;
}

// Die Suche stand hier bis zum 21.08.2026 als eigene Fassung — eine von neun
// wortgleichen im Bereich. Seit die Schulden-Seite auch die Herkunft der
// HAUSHALTSSATZUNG nachschlägt (anderer Endpunkt, anderer Antworttyp), passt
// eine auf `SchuldenDaten` festgenagelte Fassung nicht mehr. Die gemeinsame in
// `lib/haushalt.ts` ist strukturell getypt und deckt beide Fälle.
export { herkunftVon } from "@/lib/haushalt";

/** Was auf der Y-Achse steht: die Gesamtschuld oder der Betrag je Person.
 *
 *  Beide gehören auf diese Seite, weil sie über dreißig Jahre verschiedene
 *  Richtungen zeigen — die Einwohnerzahl ist in derselben Zeit deutlich
 *  gewachsen. Nur die absolute Reihe zu zeigen hieße, das Wachstum der Stadt
 *  als Schuldenaufbau zu lesen; nur die Pro-Kopf-Reihe zu zeigen, den
 *  absoluten Anstieg zu verschweigen. */
export type Ansicht = "total" | "per_capita";

export type Punkt = { year: number; value: number };

export function punkte(series: SchuldenJahr[], ansicht: Ansicht): Punkt[] {
  return series
    .map((z) => ({
      year: z.year,
      // Absolutbeträge in Mio., Pro-Kopf-Beträge in Euro — sonst stünde die
      // eine Reihe bei 337 und die andere bei 0,0019.
      value: ansicht === "total" ? z.total / 1e6 : (z.per_capita ?? NaN),
    }))
    .filter((p) => Number.isFinite(p.value));
}

/** Der Kernhaushalt: alles außer den Eigenbetrieben.
 *
 *  Die drei Spalten „Kreditmarkt", „öffentliche Sondermittel" und
 *  „Gebietskörperschaften" sind die Schulden der Verwaltung selbst; die
 *  vierte sind die der Eigenbetriebe. Rechtlich schuldet die Stadt beides —
 *  die Trennung erklärt aber den Sprung von 2010, als die Stadt einen
 *  Eigenbetrieb gründete und 108,9 Mio. € Kredite dorthin übertrug.
 *  `null`, wo die Aufteilung nicht belegt ist. */
export function core_budget(z: SchuldenJahr): number | null {
  if (z.credit_market == null) return null;
  return z.credit_market + (z.special_funds ?? 0) + (z.public_authorities ?? 0);
}

export type Aufteilung = { year: number; kern: number; municipal_enterprises: number };

/** Nur die Jahre, für die eine belegte Aufteilung vorliegt. */
export function aufteilungen(series: SchuldenJahr[]): Aufteilung[] {
  const aus: Aufteilung[] = [];
  for (const z of series) {
    const kern = core_budget(z);
    if (kern == null || z.municipal_enterprises == null) continue;
    aus.push({ year: z.year, kern, municipal_enterprises: z.municipal_enterprises });
  }
  return aus;
}

/** Die Jahre ohne belegte Aufteilung — die Seite benennt sie, statt einen
 *  leeren Balken unkommentiert zu lassen. */
export function ohneAufteilung(series: SchuldenJahr[]): SchuldenJahr[] {
  return series.filter((z) => z.breakdown_rejected != null);
}

/** Die größte Veränderung von einem Jahr aufs nächste — aus den Daten
 *  gerechnet, nicht aus dem Gedächtnis beschriftet. `richtung` sagt, wonach
 *  gesucht wird. */
export function groessterSprung(
  p: Punkt[], richtung: "rauf" | "runter",
): { year: number; delta: number } | null {
  let treffer: { year: number; delta: number } | null = null;
  for (let i = 1; i < p.length; i++) {
    const delta = p[i].value - p[i - 1].value;
    if (richtung === "runter" ? delta >= 0 : delta <= 0) continue;
    if (!treffer || Math.abs(delta) > Math.abs(treffer.delta)) {
      treffer = { year: p[i].year, delta };
    }
  }
  return treffer;
}

/** Deutsche Anzeige eines Euro-Betrags ohne Nachkommastellen („1.908"). */
export function deEuro(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return Math.round(v).toLocaleString("de-DE");
}
