"use client";

// Der Jahreskreis: eine Haushaltsrunde auf einem Kalenderjahr.
//
// Warum ein Kreis und kein Zeitstrahl: Der interessante Befund dieser Seite
// ist nicht die Dauer, sondern die LAGE — dass die Beratung im Herbst des
// Vorjahres beginnt und der Beschluss regelmäßig erst fällt, wenn das
// Haushaltsjahr schon läuft. Auf einem Strahl ist das eine Strecke unter
// vielen; auf dem Kreis überquert der Bogen sichtbar den Jahresbeginn. Genau
// deshalb trägt der Kreis oben eine beschriftete Marke: Ohne sie wäre er
// hübsch und aussagelos.
//
// Der Kreis ist EIN Kalenderjahr, nicht die Dauer der Runde. Eine Station im
// Oktober des Vorjahres steht deshalb an derselben Stelle wie eine im Oktober
// des Haushaltsjahres — die Jahreszahl steht darum an jeder Station in der
// Liste daneben, nie nur im Kreis.
//
// Keine Bewertungsfarben: Der Bogen ist durchgehend Hafenblau. Ob ein
// Beschluss jemandem passt, sagt der Kreis nicht. Die Ergebnis-Abzeichen in
// der Liste folgen der App-Grammatik (Angenommen/Vertagt/…), zeigen aber den
// Wortlaut des Ratsinformationssystems, nicht unsere Übersetzung.

import { deDatum, ergebnisArt, jahresAnteil, WegRunde, WegStation } from "@/lib/haushalt-jahr";
import { OUTCOME_META } from "@/components/decision-ui";
import { cn } from "@/lib/utils";

const MITTE = 160;
// Der Radius ist so gewählt, dass ÜBER den Monatsbuchstaben noch eine Zeile
// frei bleibt: Dort steht die Marke „1. Januar", und bei r = 116 lag sie
// mitten im „D" und im „J".
const RADIUS = 102;
const BAND = 20;

/** Anteil eines Datums am Haushaltsjahr — Werte < 0 liegen im Vorjahr. */
function lage(iso: string, jahr: number): number {
  return jahresAnteil(iso) + (Number(iso.slice(0, 4)) - jahr);
}

function punkt(anteil: number, radius: number): [number, number] {
  const rad = (anteil * 360 - 90) * (Math.PI / 180);
  return [MITTE + radius * Math.cos(rad), MITTE + radius * Math.sin(rad)];
}

function bogen(von: number, bis: number, radius: number): string {
  const [x0, y0] = punkt(von, radius);
  const [x1, y1] = punkt(bis, radius);
  const gross = bis - von > 0.5 ? 1 : 0;
  return `M ${x0} ${y0} A ${radius} ${radius} 0 ${gross} 1 ${x1} ${y1}`;
}

const MONATSKUERZEL = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

export function Jahreskreis({ runde, className }: { runde: WegRunde; className?: string }) {
  const stationen = runde.stationen;
  const letzte = stationen[stationen.length - 1];
  if (!letzte) return null;

  const start = runde.einbringung ?? stationen[0];
  const von = lage(start.datum, runde.jahr);
  const bis = lage(letzte.datum, runde.jahr);
  const fach = runde.fachausschuesse;

  return (
    <svg
      viewBox="0 0 320 320"
      className={cn("h-auto w-full max-w-[320px]", className)}
      role="img"
      aria-label={
        `Der Haushalt ${runde.jahr} auf dem Kalenderjahr: erste Station am ` +
        `${deDatum(start.datum)}, letzte am ${deDatum(letzte.datum)}. ` +
        `Die Stationen im Einzelnen stehen als Liste daneben.`
      }
    >
      {/* Das Kalenderjahr als Grundring. */}
      <circle cx={MITTE} cy={MITTE} r={RADIUS} fill="none" strokeWidth={BAND}
        className="stroke-muted" />

      {/* Die Runde als Bogen — von der Einbringung bis zur letzten Station. */}
      <path d={bogen(von, bis, RADIUS)} fill="none" strokeWidth={BAND}
        strokeLinecap="round" className="stroke-primary/25" />

      {/* Die Fachausschuss-Runde liegt innen: eigene Spur, damit sie den
          Beschlussweg nicht überschreibt. Ein einzelner Termin hat keine
          Länge — dann bleibt der Punkt, den die Stationen ohnehin setzen. */}
      {fach && fach.von !== fach.bis && (
        <path
          d={bogen(lage(fach.von, runde.jahr), lage(fach.bis, runde.jahr), RADIUS - BAND)}
          fill="none" strokeWidth={5} strokeLinecap="round"
          className="stroke-primary/35"
        />
      )}

      {/* Monatsanfänge als feine Teiler, plus die Anfangsbuchstaben. */}
      {MONATSKUERZEL.map((k, i) => {
        const a = i / 12;
        const [xi, yi] = punkt(a, RADIUS - BAND / 2);
        const [xa, ya] = punkt(a, RADIUS + BAND / 2);
        const [xt, yt] = punkt(a + 1 / 24, RADIUS + BAND / 2 + 13);
        return (
          <g key={i}>
            <line x1={xi} y1={yi} x2={xa} y2={ya} strokeWidth={1}
              className="stroke-background/70" />
            <text x={xt} y={yt} textAnchor="middle" dominantBaseline="middle"
              fontSize={10} className="fill-muted-foreground font-mono">
              {k}
            </text>
          </g>
        );
      })}

      {/* Die Marke, die den Kreis erst lesbar macht: Hier beginnt das
          Haushaltsjahr. Alles links davon ist Vorjahr. */}
      <line x1={MITTE} y1={MITTE - RADIUS - BAND / 2 - 4} x2={MITTE} y2={MITTE - RADIUS + BAND / 2 + 4}
        strokeWidth={1.5} className="stroke-foreground/45" />
      <text x={MITTE} y={15} textAnchor="middle" fontSize={9.5}
        className="fill-muted-foreground font-mono uppercase tracking-[0.09em]">
        1. Januar {runde.jahr}
      </text>

      {/* Einbringung: offener Punkt — öffentlich einsehbar, aber noch kein Beschluss. */}
      {runde.einbringung && (
        <Punkt anteil={von} art="offen" />
      )}

      {stationen.map((s, i) => (
        <Punkt
          key={`${s.ksinr}-${i}`}
          anteil={lage(s.datum, runde.jahr)}
          art={i === stationen.length - 1 ? "letzte" : "voll"}
        />
      ))}

      <text x={MITTE} y={MITTE - 8} textAnchor="middle" fontSize={13}
        className="fill-muted-foreground">
        Haushaltsjahr
      </text>
      <text x={MITTE} y={MITTE + 22} textAnchor="middle" fontSize={30} fontWeight={700}
        className="fill-foreground font-display tabular-nums">
        {runde.jahr}
      </text>
    </svg>
  );
}

function Punkt({ anteil, art }: { anteil: number; art: "offen" | "voll" | "letzte" }) {
  const [x, y] = punkt(anteil, RADIUS);
  if (art === "offen") {
    return <circle cx={x} cy={y} r={5.5} strokeWidth={2} className="fill-card stroke-primary" />;
  }
  return (
    <>
      {art === "letzte" && <circle cx={x} cy={y} r={11} className="fill-primary/20" />}
      <circle cx={x} cy={y} r={art === "letzte" ? 6.5 : 4.5} className="fill-primary" />
    </>
  );
}

/** Ergebnis-Abzeichen im Wortlaut des Ratsinformationssystems.
 *  Die Farbe folgt der Ergebnis-Grammatik der App, der Text nicht: „geändert
 *  beschlossen" ist genauer als „Angenommen" und die Formulierung, unter der
 *  man den Punkt im Original wiederfindet. */
export function ErgebnisAbzeichen({ ergebnis, className }: {
  ergebnis: string | null;
  className?: string;
}) {
  if (!ergebnis) return null;
  return (
    <span className={cn(
      "shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium",
      OUTCOME_META[ergebnisArt(ergebnis)].cls,
      className,
    )}>
      {ergebnis}
    </span>
  );
}

/** Eine Station als Zeile — Datum, Gremium, Ergebnis, und wenn es in dieser
 *  Sitzung eine Abstimmung über die Haushaltssatzung gab, deren Zählung.
 *
 *  Das Abzeichen steht neben dem Kicker und darf umbrechen, nicht neben dem
 *  Gremium: „zurückgestellt/abgesetzt" ist breiter als die halbe Zeile, und
 *  daneben brach „Ausschuss für Finanzen und Beteiligungen" auf 375 px in
 *  drei Zeilen um. */
export function StationsZeile({ station, rolle, children }: {
  station: WegStation;
  /** Was die Station im Verfahren ist — steht über dem Gremium. */
  rolle: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="border-t border-border/70 py-3 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {rolle}
        </p>
        <ErgebnisAbzeichen ergebnis={station.ergebnis} />
      </div>
      <p className="mt-1 text-[13.5px] font-bold leading-snug">{station.gremium}</p>
      {children}
    </div>
  );
}
