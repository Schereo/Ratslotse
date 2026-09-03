// <PunkteBilanz> — die Verhandlungsbilanz: Punkte statt Prozente (GB-09).
//
// Jeder Punkt ist EINE Abstimmung über eine Änderungsliste; gefüllt heißt:
// fand eine Mehrheit. Mehr sagt die Grafik nicht — und genau das ist ihr
// Vertrag. Eine Erfolgsquote läse sich wie ein Zeugnis, dabei ist
// „eingebracht und abgelehnt" parlamentarischer Alltag der Opposition
// (H3-04). Deshalb ist FAIRNESS HIER API, NICHT DOKU:
//
//  * **Keine Prozent-Prop.** Es gibt kein Feld, in das eine Quote passte,
//    und die Komponente rechnet auch keine aus. Wer eine will, muss diese
//    Datei ändern — und liest dann diesen Absatz.
//  * **Sortierung alphabetisch, fest.** Kein `sortierung`-Prop: Die
//    Komponente sortiert selbst (de-Kollation). Eine Reihenfolge nach
//    Erfolg oder Größe wäre eine Wertung; die Eingabereihenfolge könnte
//    eine sein — beides ist damit nicht konstruierbar.
//  * **Gleiche Punktgröße erzwungen** (11 px auf jedem Gerät, H4-A), gleiche
//    Zeilenhöhe, gleiche Kartenform. Kein Layout bevorzugt eine Fraktion.
//  * **Fraktionsfarbe nur als 8-px-Identitätspunkt**, nie als Fläche
//    (Designsprache § 2/§ 7). Die Bilanz-Punkte selbst sind neutral: Gefüllt
//    oder nicht ist eine Tatsache, keine Note — deshalb auch kein Grün/Rot.
//
// GEZÄHLT WERDEN ABSTIMMUNGEN, KEINE LISTEN: Dieselbe Änderungsliste kann im
// Finanzausschuss und im Rat aufgerufen werden und zählt dann an beiden
// Stellen — die Fußzeile sagt das dazu, damit niemand die Spalten addiert
// und „Listen" liest. Ein Punkt ohne Füllung heißt „fand keine Mehrheit":
// abgelehnt, vertagt oder ohne protokolliertes Ergebnis — die Legende
// benennt alle drei, geraten wird keins.
//
// Breakpoint-Verhalten (H4-A, eingebaut, kein Prop): ab 744 px das
// Bilanz-Grid (Fraktion · Finanzausschuss · Rat · Zahlen), darunter je
// Fraktion eine Karte mit zwei Dot-Zeilen FA/RAT.
//
// TABELLEN-LESBARKEIT (Tims Befund 26.08.2026): Die Zahlenspalte hieß
// „Ein · durch" und trug beide Werte in EINER Zelle („2 · 0") — nicht zu
// entziffern, welche Zahl welche ist, und die Wörter erklärten sich nicht.
// Jetzt sind es zwei Spalten mit ausgeschriebenen Köpfen („Eingebracht",
// „Mit Mehrheit" — dieselben Worte wie in der Legende), und jede Spalte
// nach der Fraktion trägt eine Spaltenlinie. Das ändert nichts an den
// Fairness-Regeln oben: Es sind weiter absolute Zahlen, keine Quote.

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Eine Seite der Bilanz: wie viele Abstimmungen, wie viele mit Mehrheit. */
export type PunkteStand = { ein: number; durch: number };

export type PunkteZeile = {
  /** Fraktion, Gruppe oder kombiniertes Label der gemeinsamen Liste. */
  fraktion: string;
  /** Identitätspunkt (8 px). Ohne Angabe neutral — Gruppen und kombinierte
   *  Labels bekommen NIE die Farbe der erstgenannten Partei. */
  farbe?: { bg: string; ring?: boolean };
  committees: { fa: PunkteStand; rat: PunkteStand };
};

/** Punktgröße in px — fest, auf jedem Gerät (H4-A: „Fairness-Regel gilt auf
 *  jedem Gerät"). Bewusst keine Prop. */
const PUNKT = 11;

const NEUTRAL = "hsl(209 18% 65%)";

/** Spaltenlinie + Innenabstand jeder Zelle nach der Fraktions-Spalte. */
const TRENNER = "border-l border-border/40 px-3";

function IdentitaetsPunkt({ farbe }: { farbe?: { bg: string; ring?: boolean } }) {
  return (
    <span
      aria-hidden
      className="h-2 w-2 flex-none rounded-full"
      style={{
        background: farbe?.bg ?? NEUTRAL,
        boxShadow: farbe?.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
      }}
    />
  );
}

/** Eine Dot-Zeile: erst die Abstimmungen mit Mehrheit (gefüllt), dann die
 *  ohne (Umriss). Die Punkte sind dekorativ — der Satz für die Vorlesehilfe
 *  steht als sr-only daneben, mit denselben Zahlen. */
function Punkte({ as_of, kontext }: { as_of: PunkteStand; kontext: string }) {
  const ohne = Math.max(as_of.ein - as_of.durch, 0);
  return (
    <>
      <span aria-hidden className="flex flex-wrap items-center gap-1">
        {Array.from({ length: as_of.durch }, (_, i) => (
          <span
            key={`d${i}`}
            className="flex-none rounded-full bg-foreground/75"
            style={{ width: PUNKT, height: PUNKT }}
          />
        ))}
        {Array.from({ length: ohne }, (_, i) => (
          <span
            key={`o${i}`}
            className="flex-none rounded-full border-[1.5px] border-foreground/40"
            style={{ width: PUNKT, height: PUNKT }}
          />
        ))}
        {as_of.ein === 0 && (
          <span className="text-[11px] leading-none text-muted-foreground">—</span>
        )}
      </span>
      <span className="sr-only">
        {kontext}: {as_of.ein === 0
          ? "keine Änderungsliste zur Abstimmung"
          : `${as_of.ein === 1 ? "1 Abstimmung" : `${as_of.ein} Abstimmungen`} über Änderungslisten, `
            + `${as_of.durch} davon ${as_of.durch === 1 ? "fand" : "fanden"} eine Mehrheit`}
      </span>
    </>
  );
}

function summe(z: PunkteZeile): PunkteStand {
  return {
    ein: z.committees.fa.ein + z.committees.rat.ein,
    durch: z.committees.fa.durch + z.committees.rat.durch,
  };
}

export function PunkteBilanz({ zeilen, beleg, className }: {
  zeilen: PunkteZeile[];
  /** Beleg-Chip der Seite — steht an der Legende (GB-00). */
  beleg?: ReactNode;
  className?: string;
}) {
  // Alphabetisch, IMMER — s. Kopfkommentar. `localeCompare` mit de-Kollation,
  // damit Umlaute nicht ans Ende rutschen.
  const sortiert = [...zeilen].sort((a, b) => a.fraktion.localeCompare(b.fraktion, "de"));
  if (!sortiert.length) return null;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* ≥ 744 px: das Bilanz-Grid (H4-15: Fraktion 170 px · FA · Rat ·
          Zahlen 84 px; Tablet mindestens 200 px je Gremienspalte).

          DIE MINDESTBREITEN SIND GESENKT (30.08.2026), und die
          `breit:`-Variante ist weg. Gemessen lief das Raster bei genau zwei
          Breiten aus der Karte heraus: bei 744 px (Summe der Minima 711 bei
          662 px Platz) und bei 1024 px, wo die `breit:`-Variante ihre Minima
          ANHEBT — ausgerechnet dort, wo die Desktop-Seitenleiste einsetzt und
          nur noch 686 px übrig lässt (771 gebraucht). Ein Minimum, das
          Überlauf erzeugt, dient der Lesbarkeit nicht mehr: Es greift genau
          dann, wenn es eng ist, und da soll es klein sein.

          Für die Boards ändert das nichts, wo Platz ist: Die Gremienspalten
          wachsen über `1fr` von selbst — auf dem Tablet (834 px) auf 200 px,
          am Desktop (1280 px) auf 285 px. Die 200 aus H4-15 sind dort also
          weiterhin erfüllt, nur nicht mehr erzwungen, wo sie nicht passen. */}
      <div className="hidden [@media(min-width:744px)]:block">
        <div
          role="table"
          aria-label="Verhandlungsbilanz: Abstimmungen über Änderungslisten je Fraktion"
          className="grid grid-cols-[150px_minmax(140px,1fr)_minmax(140px,1fr)_max-content_max-content]"
        >
          {/* Spaltenlinien: jede Zelle nach der Fraktion trägt border-l —
              ein Grid ohne gap, der Abstand kommt aus dem Zellen-Padding,
              damit die Linien von Kopf bis Fuß durchlaufen. */}
          <div role="row" className="contents">
            <KopfZelle className="pr-3">Fraktion · alphabetisch</KopfZelle>
            <KopfZelle className={TRENNER}>Im Finanzausschuss</KopfZelle>
            <KopfZelle className={TRENNER}>Im Rat</KopfZelle>
            <KopfZelle className={cn(TRENNER, "text-right")}>Eingebracht</KopfZelle>
            <KopfZelle className={cn(TRENNER, "text-right")}>Mit Mehrheit</KopfZelle>
          </div>
          {sortiert.map((z) => {
            const s = summe(z);
            return (
              <div role="row" className="contents" key={z.fraktion}>
                {/* Gleiche Zeilenhöhe für alle: min-h statt Inhaltshöhe,
                    damit eine Fraktion mit 18 Punkten keine optisch
                    „schwerere" Zeile bekommt als eine mit 2. */}
                <div role="rowheader" className="flex min-h-[38px] items-center gap-1.5 border-t border-border/60 pr-3">
                  <IdentitaetsPunkt farbe={z.farbe} />
                  <span className="min-w-0 text-[12.5px] font-semibold leading-tight">
                    {z.fraktion}
                  </span>
                </div>
                <div role="cell" className={cn("flex min-h-[38px] items-center border-t border-border/60", TRENNER)}>
                  <Punkte as_of={z.committees.fa} kontext="Im Finanzausschuss" />
                </div>
                <div role="cell" className={cn("flex min-h-[38px] items-center border-t border-border/60", TRENNER)}>
                  <Punkte as_of={z.committees.rat} kontext="Im Rat" />
                </div>
                <div role="cell" className={cn("flex min-h-[38px] items-center justify-end border-t border-border/60 font-mono text-[12px] tabular-nums", TRENNER)}>
                  {s.ein}
                </div>
                <div role="cell" className={cn("flex min-h-[38px] items-center justify-end border-t border-border/60 font-mono text-[12px] tabular-nums", TRENNER)}>
                  {s.durch}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* < 744 px: je Fraktion eine Karte — Kopfzeile, darunter zwei
          Dot-Zeilen mit Mini-Label FA/RAT (H4-A). Gleiche Kartenform für
          alle, alphabetisch — Fairness gilt auch mobil. */}
      <ul className="flex flex-col gap-2 [@media(min-width:744px)]:hidden">
        {sortiert.map((z) => {
          const s = summe(z);
          return (
            <li key={z.fraktion} className="rounded-xl border border-border/70 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold">
                  <IdentitaetsPunkt farbe={z.farbe} />
                  {z.fraktion}
                </span>
                <span className="font-mono text-[10.5px] tabular-nums text-muted-foreground">
                  {s.ein} eingebracht · {s.durch} mit Mehrheit
                </span>
              </div>
              <div className="mt-2 grid grid-cols-[34px_1fr] items-center gap-y-1.5">
                <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                  FA
                </span>
                <Punkte as_of={z.committees.fa} kontext="Im Finanzausschuss" />
                <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                  Rat
                </span>
                <Punkte as_of={z.committees.rat} kontext="Im Rat" />
              </div>
            </li>
          );
        })}
      </ul>

      {/* Legende + Zählregel — Teil der Grafik, nicht der Seite: Ohne den
          Satz zur Zählweise addiert jemand FA und Rat zu „Listen". */}
      <div className="flex flex-col gap-1.5 border-t border-dashed border-border pt-2.5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-[11px] w-[11px] flex-none rounded-full bg-foreground/75" />
            fand eine Mehrheit
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-[11px] w-[11px] flex-none rounded-full border-[1.5px] border-foreground/40" />
            eingebracht, ohne Mehrheit — abgelehnt, vertagt oder ohne protokolliertes Ergebnis
          </span>
          {beleg}
        </div>
        <p className="max-w-[86ch] text-[11px] leading-relaxed text-muted-foreground">
          Gezählt sind Abstimmungen, keine Listen: Dieselbe Änderungsliste kann im
          Finanzausschuss und im Rat aufgerufen werden und zählt dann an beiden Stellen.
        </p>
      </div>
    </div>
  );
}

function KopfZelle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      role="columnheader"
      className={cn(
        "pb-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </div>
  );
}
