import type { ApiAntwort } from "@/lib/vertrag";

/** Die Ebene „Wahlergebnis" der Stadtkarte (STADTKARTE-PLAN.md, Schritt 7):
 *  das Ergebnis der Ratswahl je Wahlbereich, auf die Ortsbereiche gelegt.
 *
 *  Die Stadt schneidet ihre sechs Wahlbereiche aus Wahlbezirken, nicht aus
 *  Ortsbereichen; der Ortskatalog nennt je Ortsbereich, in welchen
 *  Wahlbereichen er liegt — Grenzgebiete in mehreren. Für die Fläche zählt
 *  der ERSTE (der Hauptteil), die Tafel nennt alle. Das ist ungefähr, und die
 *  Quellenzeile sagt es.
 *
 *  Reine Funktionen — die Karte färbt, die Tafel listet, beide rechnen hier.
 */
export type Wahlstand = ApiAntwort<"/wahlabend">;
export type Wahlbereich = Wahlstand["areas"][number];

export type WahlListe = {
  slug: string;
  short: string;
  name: string;
  color: string;
  colorDark: string;
  /** Anteil in Prozent — `null`, solange nichts ausgezählt ist. */
  share: number | null;
  seats: number | null;
};

export type WahlFlaeche = {
  wahlbereich: number;
  roman: string;
  name: string;
  counted: number;
  total: number;
  /** Die Listen nach Anteil, stärkste zuerst. */
  listen: WahlListe[];
  /** Anteil der stärksten Liste als Bruch 0..1 — die Tönung der Fläche. */
  staerke: number;
};

/** Die Listen eines Wahlbereichs (oder der Stadt), nach Anteil sortiert; die
 *  Stammdaten (Kurzname, Farbe) kommen aus der stadtweiten Liste. */
export function listenSortiert(
  parteien: Wahlstand["parties"],
  anteile: { slug: string; share_pct: number | null; seats: number | null }[],
): WahlListe[] {
  const stamm = new Map(parteien.map((p) => [p.slug, p]));
  return anteile
    .map((a) => {
      const p = stamm.get(a.slug);
      return {
        slug: a.slug, short: p?.short ?? a.slug, name: p?.name ?? a.slug,
        color: p?.color ?? "#64748b", colorDark: p?.color_dark ?? "#94a3b8",
        share: a.share_pct, seats: a.seats,
      };
    })
    .sort((a, b) => (b.share ?? -1) - (a.share ?? -1));
}

/** Je Wahlbereich eine Fläche — noch ohne Ortsbereiche. */
export function wahlbereiche(stand: Wahlstand): Map<number, WahlFlaeche> {
  const m = new Map<number, WahlFlaeche>();
  for (const a of stand.areas) {
    const listen = listenSortiert(stand.parties, a.parties);
    m.set(a.number, {
      wahlbereich: a.number, roman: a.roman, name: a.name,
      counted: a.districts_counted, total: a.districts_total, listen,
      staerke: Math.max(0, Math.min(1, (listen[0]?.share ?? 0) / 100)),
    });
  }
  return m;
}

/** Ortsbereich-Name → seine Wahl-Fläche (über den ersten Wahlbereich des Katalogs). */
export function wahlFlaechen(
  stand: Wahlstand,
  katalog: { name: string; electoral_districts: number[] }[],
): Map<string, WahlFlaeche> {
  const bereiche = wahlbereiche(stand);
  const m = new Map<string, WahlFlaeche>();
  for (const ort of katalog) {
    const f = bereiche.get(ort.electoral_districts[0]);
    if (f) m.set(ort.name, f);
  }
  return m;
}

/** Die Tönung einer Fläche: ab einem Viertel der Stimmen deutlich, bei der
 *  Hälfte satt — darunter wäre alles gleich blass, darüber alles gleich satt. */
export function toenungNachStaerke(staerke: number): number {
  if (staerke <= 0) return 0.04;
  return 0.1 + 0.55 * Math.max(0, Math.min(1, (staerke - 0.15) / 0.35));
}

export function prozent(share: number | null): string {
  return share == null ? "–" : `${share.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}
