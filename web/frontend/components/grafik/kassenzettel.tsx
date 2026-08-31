// <Kassenzettel> — eine Summe als Bon, Zeile für Zeile (GB-13).
//
// Die Form für „eine große Zahl, durch eine Bezugsgröße geteilt": dieselbe
// Reihenfolge, dieselben Verhältnisse wie die Quelle, nur in einer Einheit,
// die man mit dem eigenen Leben vergleichen kann. Entstanden als Pro-Kopf-
// Zettel des Haushalts (H2-02); mit dem Baukasten hierher verallgemeinert —
// die SEITE rechnet und wählt die Posten, der Zettel rendert.
//
// DREI PFLICHTEN, DIE DIE KOMPONENTE ERZWINGT (GB-13 wörtlich):
//
//  * `teiler` — Bezugsgröße, Stichtag und Quelle stehen SICHTBAR unter dem
//    Zettel, nicht in einer Fußnote daneben: Der Bon ist das eine Format des
//    Bereichs, das man als Screenshot weiterschickt, und die Division muss
//    mitreisen.
//  * `nichtAussagen` — die Pro-Kopf-Zahl ist die missbrauchbarste des ganzen
//    Bereichs und reist nie ohne ihren „Was diese Zahl nicht ist"-Kasten.
//    Pflicht-Prop: Ein Zettel ohne ihn kompiliert nicht. Nie einklappbar
//    (H4-A), Signal-Rand als Markierung — keine Bewertung.
//  * Die RUNDUNGSZEILE rechnet die Komponente selbst: Weichen Einzelposten
//    und Gesamtsumme ab (jede Zeile ist für sich gerundet), steht das am
//    Zettel, statt dass jemand daran denken muss.
//
// KEIN STRICHCODE, KEINE DEKO: Die gezackte Papierkante ist das einzige
// Zierelement. Ein Strichcode sähe aus, als kodierte er etwas — auf einer
// Seite, deren ganzer Punkt Nachprüfbarkeit ist, wäre das der falsche Scherz.
//
// Signal-Orange nur an Differenz-Zeilen (`ton: "signal"`, „aus dem
// Ersparten") und am Rand des Kastens — nie als Bewertung.

import type { ReactNode } from "react";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";

export type BonZeile = {
  label: ReactNode;
  wert: number;
  /** `signal` = Differenz („aus dem Ersparten"), `leise` = kleiner Posten. */
  ton?: "signal" | "leise";
};

export type NichtAussage = {
  /** Der fette Kopfsatz: „Geteilt wird durch alle." */
  kern: string;
  text: string;
};

/** Gezackte Papierkante — rein dekorativ, s. Kopfkommentar. */
function Papierkante({ unten }: { unten?: boolean }) {
  const zacken = Array.from({ length: 31 }, (_, i) =>
    `L${(i + 1) * 12} ${i % 2 === 0 ? 0 : 8}`).join(" ");
  return (
    <svg viewBox="0 0 372 8" preserveAspectRatio="none" aria-hidden="true"
      className={cn("block h-2 w-full text-card", unten && "rotate-180")}>
      <path d={`M0 8 L0 0 ${zacken} L372 8 Z`} fill="currentColor" />
    </svg>
  );
}

/** Eine Zeile des Bons: Bezeichnung, Punktlinie, Betrag. */
function Bonzeile({ z }: { z: BonZeile }) {
  return (
    <div className={cn(
      "flex items-baseline gap-1.5",
      z.ton === "signal" && "text-signal",
      z.ton === "leise" && "text-muted-foreground",
    )}>
      <span className="flex-none">{z.label}</span>
      <span aria-hidden="true" className={cn(
        "min-w-3 flex-1 -translate-y-[3px] border-b border-dotted",
        z.ton === "signal" ? "border-signal/50" : "border-border",
      )} />
      <span className="flex-none font-medium tabular-nums">{deZahl(z.wert)}</span>
    </div>
  );
}

export function Kassenzettel({
  titel, untertitel, stempel, posten, summe, summeLabel = "Summe",
  bezahltMit, bezahltMitTitel = "Bezahlt mit", teiler, nichtAussagen,
  fuss, quelle, daneben, danach, darunter, className,
}: {
  /** Kopf des Bons: „Stadt Oldenburg" / „Haushaltsplan 2026". */
  titel: string;
  untertitel: string;
  /** Der Signal-Stempel unter dem Kopf („je Einwohner*in"), samt Beleg. */
  stempel?: ReactNode;
  /** Die Zeilen, in der Reihenfolge der Quelle — der Zettel sortiert nicht. */
  posten: BonZeile[];
  /** Die ausgewiesene Gesamtsumme — NICHT hier aus den (je für sich
   *  gerundeten) Posten summiert; die Abweichung nennt die Rundungszeile. */
  summe: number;
  summeLabel?: ReactNode;
  /** Der Block unter der Summe: Einnahmen, „aus dem Ersparten" (Signal). */
  bezahltMit?: BonZeile[];
  bezahltMitTitel?: string;
  /** PFLICHT: Bezugsgröße, Stichtag, Quelle — sichtbar unter dem Zettel. */
  teiler: { zahl: number; einheit: string; as_of_date: string; quelle: ReactNode };
  /** PFLICHT: der „Was diese Zahl nicht ist"-Kasten, je Punkt ein Satz. */
  nichtAussagen: NichtAussage[];
  /** Weitere Bon-Abschnitte vor der Quellzeile (z. B. Rücklagen-Stand). */
  fuss?: ReactNode;
  /** Quellzeile am Bon-Fuß. */
  quelle?: string;
  /** Inhalt der Spalte neben dem Bon, ÜBER dem Kasten (Titel, Einordnung). */
  daneben?: ReactNode;
  /** Inhalt der Spalte neben dem Bon, UNTER dem Kasten (Rechen-Karten). */
  danach?: ReactNode;
  /** Inhalt unter Bon UND Begleitspalte. Für breite Grafiken, die auf großen
   *  Screens auch den sonst freien Raum unter dem Bon nutzen sollen. */
  darunter?: ReactNode;
  className?: string;
}) {
  const teileSumme = posten.reduce((s, p) => s + p.wert, 0);

  return (
    <div className={cn("@container/zettel", className)}>
      <div className="flex flex-col gap-5 @3xl/zettel:flex-row @3xl/zettel:gap-7">

        {/* Der Bon. Mobil steht er oben: hochkant passt er aufs Telefon
            besser als jedes Balkendiagramm (H2-02). */}
        <div className="mx-auto w-full max-w-[372px] flex-none @3xl/zettel:mx-0 @3xl/zettel:w-[352px]">
          <Papierkante />
          <div className="bg-card px-5 pb-4 font-mono text-[11.5px] leading-none text-foreground shadow-[0_18px_40px_-22px_rgba(2,32,71,0.35)]">
            <p className="text-center text-[12px] font-medium uppercase tracking-[0.16em]">
              {titel}
            </p>
            <p className="mt-1.5 text-center text-[10.5px] uppercase tracking-[0.07em] text-muted-foreground">
              {untertitel}
            </p>
            {stempel && (
              <p className="mt-3 text-center text-[10.5px] uppercase tracking-[0.07em] text-signal">
                {stempel}
              </p>
            )}

            <div className="mt-3 space-y-[7px] border-t border-dashed border-border pt-3">
              {/* Sichtbar trägt die Einheit die Kopfzeile und die Summe. Wer
                  vorgelesen bekommt, hört sonst nur „Soziales 1.603" — die
                  Währung stünde erst zwölf Zeilen später. */}
              <p className="sr-only">Ausgabenposten in Euro:</p>
              {posten.map((p, i) => <Bonzeile key={i} z={p} />)}
            </div>

            <div className="mt-3 flex items-baseline justify-between border-t border-dashed border-border pt-3">
              <span className="text-[12px] font-medium uppercase tracking-[0.08em]">
                {summeLabel}
              </span>
              <span className="font-display text-[26px] font-bold leading-none tracking-tight tabular-nums">
                {deZahl(summe)}&nbsp;€
              </span>
            </div>

            {bezahltMit && bezahltMit.length > 0 && (
              <>
                <p className="mt-3 border-t border-dashed border-border pt-3 text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
                  {bezahltMitTitel}
                </p>
                <div className="mt-2.5 space-y-[7px]">
                  {bezahltMit.map((p, i) => <Bonzeile key={i} z={p} />)}
                </div>
              </>
            )}

            {fuss}

            {/* Rundungszeile — automatisch (GB-13): Sie erscheint genau
                dann, wenn die je für sich gerundeten Posten die Gesamtsumme
                verfehlen, und verschwindet mit dem Grund. */}
            {teileSumme !== summe && (
              <p className="mt-2.5 text-[10px] leading-relaxed text-muted-foreground">
                Rundung: Die Einzelposten ergeben {deZahl(teileSumme)}&nbsp;€, die
                Gesamtsumme {deZahl(summe)}&nbsp;€.
              </p>
            )}

            {quelle && (
              <p className="mt-3 border-t border-dashed border-border pt-2.5 text-center text-[9.5px] leading-relaxed text-muted-foreground">
                {quelle}
              </p>
            )}
          </div>
          <Papierkante unten />

          {/* Der Teiler, sichtbar unter dem Zettel (GB-13): Wer nur den Bon
              sieht — Screenshot, Sharepic —, sieht auch, wodurch geteilt
              wurde und woher die Zahl stammt. */}
          <p className="mt-2 px-1 text-center text-[11px] leading-relaxed text-muted-foreground">
            Berechnet mit <span className="font-medium tabular-nums text-foreground/80">{deZahl(teiler.zahl)}</span>{" "}
            {teiler.einheit} · Stand {teiler.as_of_date} · {teiler.quelle}
          </p>
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-3.5">
          {daneben}

          {/* Der Pflicht-Kasten. Textspalten (`columns`) statt Raster
              (Designsprache §4): Die Punkte sind sehr verschieden lang,
              Spalten fließen und balancieren sich selbst. */}
          <div className="rounded-2xl border border-signal/35 bg-card p-4">
            <p className="text-[12.5px] font-bold text-signal">So ist die Pro-Kopf-Zahl einzuordnen</p>
            <ul className="mt-2.5 space-y-2.5 @2xl/zettel:columns-2 @2xl/zettel:gap-5 @2xl/zettel:space-y-0">
              {nichtAussagen.map((n) => (
                <li key={n.kern} className="flex break-inside-avoid gap-2.5 @2xl/zettel:mb-2.5">
                  <span aria-hidden="true"
                    className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-signal" />
                  <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                    <strong className="font-semibold text-foreground">{n.kern}</strong> {n.text}
                  </p>
                </li>
              ))}
            </ul>
          </div>

          {danach}
        </div>
      </div>

      {darunter && <div className="mt-3.5">{darunter}</div>}
    </div>
  );
}
