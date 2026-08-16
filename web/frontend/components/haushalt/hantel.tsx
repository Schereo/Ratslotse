"use client";

// Hantel-Diagramm „geplant und tatsächlich" (Design H-16, Empfehlung).
//
// Zwei Punkte auf einer gemeinsamen Achse, dazwischen eine Linie: Die Linie
// IST die Abweichung — Länge und Richtung liest man, ohne die Zahl zu suchen.
//
// WARUM DIE ACHSE DIE ABWEICHUNG ZEIGT UND NICHT DEN BETRAG.
// Die erste Fassung setzte beide Punkte auf eine Skala von 0 bis zum größten
// Wert. Bei echten Haushaltszahlen fallen sie damit aufeinander: Ein Bereich
// mit 6,2 geplant und 6,3 tatsächlich hat auf einer Skala bis 251 Mio. eine
// Differenz von 0,04 % der Breite — unsichtbar. Genau die Differenz ist aber
// die Aussage. Deshalb liegt der Nullpunkt bei „wie geplant", und die Strecke
// misst, wie weit es davon abwich. Die Beträge stehen als Zahl daneben; sie
// brauchen keine Pixel, um lesbar zu sein.
//
// UND WARUM IN PROZENT, NICHT IN EURO (Voreinstellung).
// Auch die Abweichung selbst spreizt in Euro zu weit: Bei den Ausgaben 2024
// reicht sie von −0,7 bis +20,5 Mio., fünf der zwölf Zeilen wären kürzer als
// zwei Prozent der Breite. Gemessen am jeweiligen Plan liegt dieselbe Spanne
// bei −10 bis +14 %, die mittlere Strecke wird fünfmal so lang, und die
// Reihenfolge ändert sich — vorn steht dann nicht der größte Bereich, sondern
// der, dessen Plan am weitesten danebenlag. Beides sind richtige Antworten auf
// verschiedene Fragen, deshalb der Umschalter.
//
// KEINE LOG-SKALA. Sie würde die kleinen Zeilen ebenfalls sichtbar machen,
// aber die Grundannahme brechen, dass die doppelte Länge den doppelten Wert
// meint — und bei Vorzeichenwechsel und Werten nahe null bräuchte es einen
// willkürlich gesetzten linearen Kern. Für ein Publikum, das keinen Haushalt
// gewohnt ist, ist das eine Falle.
//
// KEINE BEWERTUNGSFARBEN. Mehrausgaben sind nicht automatisch schlecht
// (Tarifabschluss, mehr Kita-Plätze), Minderausgaben nicht automatisch gut
// (nicht gebaut, Stellen unbesetzt). Deshalb steht Signal-Orange hier nur für
// „hier ist die Differenz", nicht für „das ist schlimm" — und Grün kommt gar
// nicht vor.

import { deMio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

export type HantelZeile = {
  label: string;
  plan: number | null;
  ist: number | null;
};

export type HantelMassstab = "prozent" | "betrag";

export function Hantel({ zeilen, klein = false, einheit = "Mio.", massstab = "prozent" }: {
  zeilen: HantelZeile[];
  klein?: boolean;
  einheit?: string;
  /** Woran die Streckenlänge hängt — siehe Kommentar oben. */
  massstab?: HantelMassstab;
}) {
  const gueltig = zeilen.filter((z) => z.plan != null && z.ist != null);
  if (!gueltig.length) return null;

  const diff = (z: HantelZeile) => Math.round(((z.ist as number) - (z.plan as number)) * 10) / 10;
  const anteil = (z: HantelZeile) =>
    z.plan ? (((z.ist as number) - (z.plan as number)) / Math.abs(z.plan as number)) * 100 : null;
  // Was die Strecke misst: den Betrag oder den Anteil am Plan. In Prozent
  // spreizen sich die Zeilen deutlich besser — bei den Ausgaben 2024 ist die
  // mittlere Strecke fünfmal so lang, und statt fünf sind nur zwei von zwölf
  // Zeilen kürzer als zwei Prozent der Breite.
  const skala = (z: HantelZeile) => (massstab === "prozent" ? anteil(z) ?? 0 : diff(z));

  // Gemeinsame Skala über alle Zeilen — sonst wären die Längen nicht
  // vergleichbar. Die Null ist immer dabei, auch wenn alle Abweichungen in
  // dieselbe Richtung gehen: Sonst verschöbe sich der Bezugspunkt.
  const werte = gueltig.map(skala);
  const min = Math.min(0, ...werte);
  const max = Math.max(0, ...werte);
  const spanne = max - min || 1;
  const pos = (v: number) => ((v - min) / spanne) * 100;
  const nullPos = pos(0);
  const skalenEnde = (v: number) =>
    massstab === "prozent"
      ? `${v > 0 ? "+" : ""}${Math.round(v)} %`
      : `${v > 0 ? "+" : ""}${deMio(v)}`;

  const gitter = klein ? "grid-cols-[minmax(38px,auto)_1fr_auto]" : "grid-cols-[minmax(96px,150px)_1fr_auto]";

  return (
    <div className={cn("flex flex-col", klein ? "gap-1.5" : "gap-2.5")}>
      {gueltig.map((z) => {
        const d = diff(z);
        const plan = z.plan as number;
        const quote = anteil(z);
        const s = skala(z);
        return (
          <div key={z.label} className={cn("grid items-center gap-x-3", gitter)}>
            <span className={cn("truncate", klein ? "text-[11.5px] tabular-nums text-muted-foreground" : "text-[12.5px]")}>
              {z.label}
            </span>
            <div aria-hidden="true" className="relative h-5">
              {/* Achse und die Marke „wie geplant" */}
              <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border/60" />
              <div className="absolute inset-y-0 w-px bg-border" style={{ left: `${nullPos}%` }} />
              {/* Die Abweichung als Strecke, ab der Null */}
              <div
                className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-signal/70"
                style={{
                  left: `${Math.min(nullPos, pos(s))}%`,
                  width: `${Math.max(Math.abs(pos(s) - nullPos), 0.5)}%`,
                }}
              />
              {/* Geplant: offener Punkt auf der Null. Tatsächlich: gefüllter
                  Punkt am Ende. Beide ohne `title`: Ein Browser-Tooltip
                  wiederholte nur, was zwei Zentimeter weiter rechts ohnehin
                  als Text steht — und zwar ausschließlich für die Maus. Auf
                  dem Telefon und für die Tastatur gab es ihn nie, für die
                  Vorlesehilfe war er eine zweite Stimme über derselben Zahl.
                  Die Punkte sind Bild zur Zeile, also `aria-hidden`. */}
              <span
                aria-hidden="true"
                className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
                style={{ left: `${nullPos}%`, borderColor: "var(--hh-ein-0)" }}
              />
              <span
                aria-hidden="true"
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ left: `${pos(s)}%`, background: "var(--hh-aus-0)" }}
              />
            </div>
            {/* Die drei Zahlen stehen dauerhaft da — hier braucht es keine
                Ablese-Leiste, die Zeile IST die Beschriftung. Die sr-only-
                Wörter sagen nur, was der Pfeil sichtbar sagt: „6,2 → 6,3
                +0,1" ist vorgelesen ohne sie nicht zuzuordnen. */}
            <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
              <span className="sr-only">geplant </span>
              <span className="text-muted-foreground">{deMio(plan)}</span>
              <span aria-hidden="true" className="mx-1 text-muted-foreground">→</span>
              <span className="sr-only">, tatsächlich </span>
              <span className="font-semibold">{deMio(z.ist as number)}</span>
              <span className="sr-only">, Abweichung </span>
              <span className={cn("ml-1.5", d !== 0 && "text-signal")}>
                {d > 0 ? "+" : ""}{deMio(d)}
              </span>
              {!klein && quote != null && (
                <span className="ml-1 text-[11px] text-muted-foreground">
                  ({quote > 0 ? "+" : "−"}{Math.abs(quote).toLocaleString("de-DE", {
                    minimumFractionDigits: 1, maximumFractionDigits: 1 })}&nbsp;%)
                </span>
              )}
            </span>
          </div>
        );
      })}

      {/* Skalenenden — ohne sie wüsste niemand, wofür die Länge steht. */}
      <div className={cn("grid gap-x-3", gitter)}>
        <span />
        <div className="relative h-4 text-[10px] tabular-nums text-muted-foreground">
          {min < 0 && <span className="absolute left-0 top-0">{skalenEnde(min)}</span>}
          <span className="absolute top-0 -translate-x-1/2 whitespace-nowrap" style={{ left: `${nullPos}%` }}>
            wie geplant
          </span>
          {max > 0 && <span className="absolute right-0 top-0">{skalenEnde(max)}</span>}
        </div>
        <span />
      </div>

      {!klein && (
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5 text-[11.5px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full border-2 bg-card" style={{ borderColor: "var(--hh-ein-0)" }} />
            geplant
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full" style={{ background: "var(--hh-aus-0)" }} />
            tatsächlich
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-[3px] w-4 rounded-full bg-signal/70" />
            {massstab === "prozent" ? "Abweichung in Prozent des Plans" : `Abweichung in ${einheit} Euro`}
          </span>
          <span className="basis-full text-[11px] leading-relaxed">
            {massstab === "prozent"
              ? "Die Strecke misst, um wie viel Prozent der Bereich von seinem Plan abwich — so ist ein Bereich von 231 Mio. mit einem von 6 Mio. vergleichbar. Der Betrag steht rechts daneben."
              : "Die Strecke misst den Betrag der Abweichung. Große Bereiche dominieren dabei; wie genau ein Bereich geplant hat, zeigt die Prozent-Ansicht besser."}{" "}
            Die Farbe bewertet nicht: Mehr ausgegeben kann ein Tarifabschluss sein oder mehr
            Kita-Plätze; weniger ausgegeben heißt oft, dass etwas nicht gebaut oder eine Stelle
            nicht besetzt wurde.
          </span>
        </div>
      )}
    </div>
  );
}
