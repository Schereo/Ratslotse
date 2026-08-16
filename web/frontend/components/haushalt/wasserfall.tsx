// Wasserfall eines Teilhaushalts: Brutto → Abzug der eigenen Erträge → Rest.
//
// Warum kein dritter Balken nebeneinander: Drei gleich lange Balken
// (Ausgaben, Einnahmen, Differenz) zwingen die Leserin, selbst zu subtrahieren
// — die Grafik zeigt dann drei Zahlen, aber nicht die Rechnung. Hier liegt die
// zweite Zeile UNTER der ersten und ist genauso breit: Was rechts blau
// abgezogen wird, bleibt links als schraffierter Rest stehen. Der Abzug ist
// eine Bewegung, keine Aufzählung.
//
// Kein SVG, sondern Kästen mit Prozentbreiten. Eine SVG-Grafik mit fester
// viewBox skaliert ihre Schrift mit: Was am Desktop 12,5 px misst, sind auf
// 375 px acht — unlesbar genau dort, wo die meisten lesen. Die Beträge stehen
// deshalb als echte Schrift in einer Legende unter dem Bild und wachsen nie
// aus ihrem Kasten heraus.
//
// Die Breiten sind exakt, ohne Mindestbreite: Ein Bereich, der 2 % seiner
// Kosten selbst deckt, bekommt einen 2-%-Streifen. Eine Mindestbreite machte
// aus „fast nichts" ein sichtbares Stück und wäre eine Behauptung.
//
// Farbe: Signal-Orange markiert die Differenz — nie eine Bewertung
// (Designsprache §2, Begründung in `hantel.tsx`). Ein Bereich mit Überschuss
// ist nicht „gut", einer mit Zuschussbedarf nicht „schlecht"; beides hängt
// daran, welche Einnahmen dort verbucht werden. Deshalb trägt der Überschuss
// dieselbe Signalfarbe wie der Zuschussbedarf.

import { deMio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

/** Ein Eintrag der Legende unter dem Bild. */
function Legende({ farbe, schraffur, label, wert, hinweis }: {
  farbe?: string;
  schraffur?: boolean;
  label: string;
  wert: number;
  hinweis?: string;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span
        aria-hidden
        className={cn(
          "mt-[3px] h-3 w-3 flex-none rounded-[3px]",
          schraffur && "hh-schraffur border border-signal/60",
        )}
        style={farbe ? { background: farbe } : undefined}
      />
      <p className="min-w-0 flex-1 text-[12.5px] leading-relaxed text-foreground/85">
        {label}
        {hinweis && <span className="text-muted-foreground"> — {hinweis}</span>}
      </p>
      <span className={cn(
        "flex-none font-display text-[15px] font-bold tabular-nums",
        schraffur && "text-signal",
      )}>
        {deMio(wert)}
      </span>
    </div>
  );
}

export function Wasserfall({ aus, ein, netto, jahr, className }: {
  /** Ordentliche Aufwendungen des Bereichs in Mio. €. */
  aus: number;
  /** Eigene ordentliche Erträge des Bereichs in Mio. €. */
  ein: number;
  /** Die Differenz in Mio. €, positiv = Zuschussbedarf.
   *
   *  Als eigener Wert und nicht hier aus `aus − ein` gerechnet: Beide Beträge
   *  sind bereits auf 0,1 Mio. gerundet, ihre Differenz rundet also ein
   *  zweites Mal. Bei den nicht rechtsfähigen Stiftungen (0,3 gegen 0,3)
   *  kippte dadurch sogar die Richtung — der Kopf der Seite schrieb
   *  „Überschuss", das Bild „trägt die Stadt". Wer die Differenz aus den
   *  Rohwerten kennt, gibt sie mit. */
  netto: number;
  jahr: number;
  className?: string;
}) {
  if (!(aus > 0) && !(ein > 0)) return null;

  // Die längere Seite spannt die Achse — daran hängen beide Zeilen, sonst
  // wären die Breiten zweier Bilder nicht vergleichbar.
  const skala = Math.max(aus, ein);
  const anteil = (v: number) => `${Math.max(Math.min((v / skala) * 100, 100), 0)}%`;
  const ueberschuss = netto < 0;
  const rest = Math.round(Math.abs(netto) * 10) / 10;
  // Ganzzahlig gerundet: „22,9 % der Kosten" suggeriert eine Genauigkeit, die
  // der Plan nicht hat (die Beträge stehen auf 100.000 € gerundet).
  const gedeckt = aus > 0 ? Math.round((ein / aus) * 100) : null;

  const oben = ueberschuss
    ? { wert: ein, label: "Eigene Erträge", farbe: "var(--hh-ein-0)" }
    : { wert: aus, label: "Ausgaben", farbe: "var(--hh-aus-0)" };
  const abzug = ueberschuss
    ? { wert: aus, label: "Ausgaben", farbe: "var(--hh-aus-0)" }
    : { wert: ein, label: "eigene Erträge", farbe: "var(--hh-ein-0)" };

  return (
    <div className={className}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {ueberschuss ? "Was reinkommt, was rausgeht" : "Was rausgeht, was reinkommt"}
        </p>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
          Mio. € {jahr}
        </span>
      </div>

      {/* Die Balken tragen bewusst KEINE Beschriftung im Inneren. Die Rampen
          `--hh-aus-*` / `--hh-ein-*` hängen am Theme und drehen sich im
          Dunkelmodus um: `--hh-aus-0` ist dort hell. Weiße Schrift darauf wäre
          im einen Modus richtig und im anderen unlesbar. Was die Farben
          bedeuten, sagt die Legende darunter — sie steht ohnehin da und wird
          auch vorgelesen. Das Bild ist damit dekorativ. */}
      <div aria-hidden className="mt-3">
        <div className="h-8 rounded" style={{ background: oben.farbe }} />
        {/* Zweite Zeile: gleiche Achse, von rechts her abgezogen. Was übrig
            bleibt, steht links — das ist der Rest, den die Allgemeinheit
            trägt. */}
        <div className="mt-1.5 flex h-8 items-stretch gap-[3px]">
          <div
            className="hh-schraffur rounded border border-dashed border-signal"
            style={{ width: `calc(${anteil(rest)} - 3px)` }}
          />
          <div className="rounded" style={{ width: anteil(abzug.wert), background: abzug.farbe }} />
        </div>
      </div>

      <div className="mt-3.5 flex flex-col gap-2 border-t border-border/60 pt-3">
        <Legende farbe={oben.farbe} label={`${oben.label} des Bereichs`} wert={oben.wert} />
        <Legende
          farbe={abzug.farbe}
          label={ueberschuss ? "Ausgaben des Bereichs" : "eigene Erträge des Bereichs"}
          hinweis={ueberschuss
            ? "was der Bereich für seine eigenen Aufgaben braucht"
            : "Gebühren, Entgelte, Erstattungen und zweckgebundene Zuschüsse"}
          wert={abzug.wert}
        />
        <Legende
          schraffur
          label={ueberschuss ? "Überschuss des Bereichs" : "trägt die Stadt"}
          hinweis={ueberschuss
            ? "steht dem allgemeinen Topf zur Verfügung"
            : "aus dem allgemeinen Topf — Steuern und Schlüsselzuweisungen"}
          wert={rest}
        />
      </div>

      {gedeckt != null && !ueberschuss && (
        <p className="mt-2.5 text-[12px] leading-relaxed text-muted-foreground">
          Von 100&nbsp;€ Ausgaben holt der Bereich {gedeckt}&nbsp;€ selbst herein.
        </p>
      )}
    </div>
  );
}
