"use client";

// Diagramm der Quiz-Auflösung — ein ADAPTER auf den Grafik-Baukasten, kein
// eigener Renderer.
//
// Diese Datei war bis 08/2026 die letzte Privat-Implementierung im Frontend:
// drei handgezeichnete Diagramme (Balkenliste, Donut, Trendlinie) mit eigenen
// Farben (`bg-amber-500`), eigener Zahlenformatierung (`Intl` inline) und
// eigenen Einstiegs-Animationen von 700–1000 ms. Alle drei Punkte stehen quer
// zum Vertrag in `components/grafik/README.md`: Farben kommen aus den Rampen-
// Tokens, Zahlen aus `components/grafik/format.ts`, Animationen dauern höchstens
// 300 ms. Statt sie einzeln nachzubessern, rendert jetzt der Baukasten:
//
//   bars  → <RanglisteSchiene> (GB-03) — sichtbare Schiene, Null-Basis, Label
//           wandert mobil über den Balken. `highlight` wird `hervorgehoben`:
//           findet, bewertet nicht.
//   trend → <Zeitreihe> (GB-01) — statt der alten Min-Max-Linie eine Achse mit
//           Null-Basis und Ableseleiste (Hover, Tap, Pfeiltasten). Fehlte ein
//           Jahr, zog die alte Linie stillschweigend durch; die Zeitreihe
//           bricht dort ab und setzt einen „?"-Kasten.
//   share → <Gegenbalken> (GB-04) — eine 100-%-Leiste mit zwei Segmenten
//           statt eines Donuts. Der Baukasten hat bewusst keine Kreisform:
//           Winkel vergleicht man schlechter als Längen.
//
// Das Chart-JSON des Backends (`council/haushalt.py`) bleibt unverändert —
// getauscht ist nur, wer es zeichnet.
//
// WARUM DER RAHMEN `bg-card` TRÄGT: Die Rampen `--hh-ein-*`/`--hh-aus-*` sind
// gegen die KARTENFLÄCHE gerechnet (weiß bzw. hsl(212 42% 11%), Kommentar in
// `app/globals.css`). Der Rahmen stand vorher auf `bg-background/60` — das
// blasse Rampenende hätte dort in beiden Themes zu wenig Abstand zum Grund.

import dynamic from "next/dynamic";
import { Gegenbalken } from "@/components/grafik/gegenbalken";
import { RanglisteSchiene, type RanglisteZeile } from "@/components/grafik/rangliste-schiene";
import type { JahrPunkt } from "@/components/grafik/daten";
import { cn } from "@/lib/utils";

// Die Zeitreihe ist die einzige der drei Formen, die d3 mitbringt (`d3-scale`
// samt `d3-format`/`d3-time-format`, `d3-shape`) — gemessen 54 kB der 60 kB,
// um die dieses Bündel sonst wüchse. Sie erscheint aber nur in zwei der
// vierzehn Haushalts-Fragen, und auch dort erst nach dem Antworten. Also
// nachladen, sobald sie gebraucht wird — dasselbe Muster wie die Leaflet-Karte
// nebenan (`quiz-play.tsx`). Balken und Anteil (~6 kB) bleiben synchron: Sie
// sind der Regelfall und sollen ohne Nachladeschritt dastehen.
const Zeitreihe = dynamic(
  () => import("@/components/grafik/zeitreihe").then((m) => m.Zeitreihe),
  { ssr: false, loading: () => <div className="h-64 w-full animate-pulse rounded-lg bg-muted" /> },
);

/** Diagramm-Daten aus dem Answer-Payload (council/haushalt.py):
 *  bars = Balken je Bereich · share = Anteil am Ganzen · trend = Jahresverlauf. */
export type QuizChartData = {
  type?: "bars" | "share" | "trend";
  title: string;
  unit: string;
  items: { label: string; value: number; highlight?: boolean }[];
};

/** Die Einheit, wie sie hinter einer Zahl steht. Das Backend schreibt sie aus
 *  („Mio. Euro"), im Diagramm wiederholt sie sich je Zeile — dort ist die
 *  Kurzform die lesbare. Unbekannte Einheiten laufen unverändert durch. */
function einheitKurz(unit: string): string {
  if (unit === "Mio. Euro") return "Mio. €";
  if (unit === "Prozent") return "%";
  return unit;
}

/** Trend-Punkte als Jahresreihe (Daten-Vertrag GB-00) — oder `null`, wenn die
 *  Labels keine Jahre sind. Dann rendert die Rangliste, statt eine Zeitachse
 *  zu behaupten, die es nicht gibt. */
function jahresreihe(items: QuizChartData["items"]): JahrPunkt[] | null {
  const reihe: JahrPunkt[] = [];
  for (const it of items) {
    const year = Number(it.label);
    if (!Number.isInteger(year) || year < 1900 || year > 2200) return null;
    reihe.push({ year, wert: it.value });
  }
  return reihe.length >= 2 ? reihe : null;
}

function Rangliste({ chart }: { chart: QuizChartData }) {
  const zeilen: RanglisteZeile[] = chart.items.map((it) => ({
    label: it.label,
    wert: it.value,
    hervorgehoben: it.highlight,
  }));
  return <RanglisteSchiene zeilen={zeilen} einheit={einheitKurz(chart.unit)} />;
}

/** Diagramm in der Quiz-Auflösung. Die Einheit trägt jede Form selbst (Zeile,
 *  Achse bzw. Basis-Zeile) — eine Fußnote „Angaben in …" wäre die zweite
 *  Beschriftung derselben Sache. */
export function QuizChart({ chart, className }: { chart: QuizChartData; className?: string }) {
  if (!chart.items?.length) return null;
  const type = chart.type ?? "bars";
  const rahmen = cn("rounded-lg border border-border bg-card p-3", className);

  if (type === "share") {
    // Das hervorgehobene Segment zuerst, damit der gefragte Bereich auch in
    // der Legende oben steht. `sort` ist stabil — die übrigen behalten ihre
    // Reihenfolge aus dem Payload.
    //
    // Die Farben stehen hier ausnahmsweise an den Segmenten: Ohne Angabe
    // verteilt der Gegenbalken seine Rampe Stufe für Stufe (`--hh-aus-0`,
    // `--hh-aus-1`, …), was bei sechs Posten trägt — bei ZWEIEN sind zwei
    // Nachbarstufen fast dieselbe Farbe, und aus 32 zu 68 wird ein Balken mit
    // Naht. Zwei weit auseinanderliegende Stufen derselben Rampe zeigen den
    // Anteil; eine Bewertung ist das nicht, beide bleiben Schiefer.
    const segmente = [...chart.items]
      .sort((a, b) => Number(!!b.highlight) - Number(!!a.highlight))
      .map((it) => ({
        label: it.label,
        wert: it.value,
        farbe: it.highlight ? "var(--hh-aus-0)" : "var(--hh-aus-5)",
      }));
    // Basis ist die SUMME der Segmente, nicht die runde 100: Rundet das
    // Backend einmal auf 99, zeigt die Leiste 99 als volle Breite statt einer
    // Lücke, die keine ist.
    const basis = segmente.reduce((s, x) => s + x.wert, 0);
    return (
      <div className={rahmen}>
        {/* Der Titel steht hier IN der Leiste (`titel`), nicht über dem
            Rahmen — sonst stünde er zweimal. */}
        <Gegenbalken
          zeilen={[{ titel: chart.title, segmente }]}
          basis={basis}
          einheit={einheitKurz(chart.unit)}
          nachkomma={0}
        />
      </div>
    );
  }

  const reihe = type === "trend" ? jahresreihe(chart.items) : null;
  return (
    <div className={rahmen}>
      <p className="text-xs font-semibold text-foreground">{chart.title}</p>
      <div className="mt-2">
        {reihe
          ? <Zeitreihe reihe={reihe} einheit={einheitKurz(chart.unit)}
              ariaTitel={chart.title} nachkomma={0} />
          : <Rangliste chart={chart} />}
      </div>
    </div>
  );
}
