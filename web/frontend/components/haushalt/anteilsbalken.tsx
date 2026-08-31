"use client";

// Ein Balken, der eine Summe in ihre Teile zerlegt — und dazuschreibt, was er
// zeigt.
//
// Warum als eigener Baustein: Dieselbe Form steht in verschiedener Bedeutung
// an mehreren Stellen des Haushalts-Bereichs — sie zerlegt einen Bau-Jahrgang
// nach Ausgabenarten (Gebaut), geplante Auszahlungen nach Vorhaben
// (Investitionsprogramm), eine Beteiligung nach Anteilseignern (Konzern) und
// den Aufwand eines Teilhaushalts nach der Spielraum-Angabe der Stadt
// (Pflicht). Jedes Mal gilt dieselbe Regel, und die ist der eigentliche
// Grund für die Komponente:
//
//  1. **Der Nenner steht dran.** Ein Anteil ohne Bezugsgröße ist keine Zahl,
//     sondern ein Gefühl. `gesamt` und `einheit` gehören deshalb in die
//     Beschriftung, nicht in den Fließtext daneben.
//  2. **Keine Bewertungsfarben.** Die Segmente kommen aus der Ausgabenrampe
//     `--hh-aus-*` (dunkel = wenig Spielraum), nie aus Ampelfarben. Ein
//     Pflichtposten ist nicht „rot", eine freiwillige Leistung nicht „grün".
//  3. **Signal-Orange nur als Marke, nie als Fläche.** Die Marke ist ein
//     2-px-Strich mit Beschriftung und heißt immer „hier ist die Differenz"
//     (Designsprache, `hantel.tsx`). Wer eine Fläche orange füllt, hat eine
//     Wertung gemalt.
//  4. **Was fehlt, wird schraffiert, nicht weggelassen.** `offen: true`
//     zeichnet ein Segment gestreift — die Lücken-Konvention aus
//     `zeitreihe.tsx`. Ein Rest, der einfach nicht gezeichnet wird, liest sich
//     als Null.
//
// Der Balken interpoliert nichts und rundet nur zur Anzeige: Die Breite kommt
// aus dem ungerundeten Wert, damit sich 13 Segmente nicht auf 100,4 % addieren.

export type Anteil = {
  label: string;
  /** In derselben Einheit wie `gesamt`. */
  wert: number;
  /** CSS-Farbe, üblicherweise `var(--hh-aus-n)`. */
  farbe: string;
  /** Schraffiert statt gefüllt — für „keine Angabe". */
  offen?: boolean;
};

export type Marke = {
  /** In derselben Einheit wie `gesamt`. */
  wert: number;
  label: string;
};

function percent(wert: number, gesamt: number): number {
  if (!gesamt) return 0;
  return Math.max(0, Math.min(100, (wert / gesamt) * 100));
}

function deProzent(p: number): string {
  return `${p.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`;
}

function schraffur(farbe: string): string {
  return `repeating-linear-gradient(45deg, ${farbe} 0 3px, transparent 3px 6px)`;
}

export function Anteilsbalken({
  segmente, gesamt, einheit = "Mio. €", mark, hoehe = 14,
  legende = true, titel, className,
}: {
  segmente: Anteil[];
  gesamt: number;
  /** Steht in der Legende hinter jedem Wert. */
  einheit?: string;
  /** Ein beschrifteter Strich quer über den Balken. */
  mark?: Marke;
  hoehe?: number;
  legende?: boolean;
  /** Mono-Kicker über dem Balken. */
  titel?: string;
  className?: string;
}) {
  const gezeigt = segmente.filter((s) => s.wert > 0);
  const beschreibung = gezeigt
    .map((s) => `${s.label} ${deProzent(percent(s.wert, gesamt))}`)
    .join(", ");

  return (
    <div className={className}>
      {titel && (
        <p className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {titel}
        </p>
      )}
      <div
        role="img"
        aria-label={`${titel ? `${titel}: ` : ""}${beschreibung || "keine Angaben"}`}
        // `relative` trägt die Marke, `overflow-hidden` schneidet die
        // Segmentkanten auf den Radius — die Marke sitzt darüber und darf
        // deshalb nicht mitgeschnitten werden.
        className="relative"
      >
        <div
          className="flex overflow-hidden rounded-full bg-muted"
          style={{ height: hoehe }}
        >
          {gezeigt.map((s, i) => (
            <div
              key={`${s.label}-${i}`}
              style={{
                width: `${percent(s.wert, gesamt)}%`,
                background: s.offen ? schraffur(s.farbe) : s.farbe,
                // Ohne Mindestbreite verschwindet ein 0,05-%-Segment ganz —
                // und mit ihm die Auskunft, dass es den Posten gibt.
                minWidth: 2,
              }}
            />
          ))}
        </div>
        {mark && gesamt > 0 && (
          <div
            className="pointer-events-none absolute top-0 z-10"
            style={{ left: `${percent(mark.wert, gesamt)}%`, height: hoehe }}
          >
            <div className="h-full w-0.5 -translate-x-1/2 bg-signal" />
          </div>
        )}
      </div>
      {mark && gesamt > 0 && (
        <p className="mt-1.5 flex items-start gap-1.5 text-[11.5px] leading-snug text-signal">
          <span aria-hidden="true" className="mt-[3px] h-3 w-0.5 flex-none bg-signal" />
          <span>{mark.label}</span>
        </p>
      )}
      {legende && gezeigt.length > 0 && (
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {gezeigt.map((s, i) => (
            <li key={`${s.label}-${i}`} className="flex items-baseline gap-2 text-[12.5px]">
              <span
                aria-hidden="true"
                className="mt-1 h-2.5 w-2.5 flex-none rounded-[3px]"
                style={{ background: s.offen ? schraffur(s.farbe) : s.farbe }}
              />
              <span className="min-w-0 flex-1 leading-snug">{s.label}</span>
              <span className="flex-none tabular-nums text-muted-foreground">
                {s.wert.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;{einheit}
              </span>
              <span className="w-[52px] flex-none text-right font-semibold tabular-nums">
                {deProzent(percent(s.wert, gesamt))}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// `AnteilsbalkenSchmal` (die 6-px-Form ohne Legende) ist am 24.08. gestrichen
// worden: Ihr einziger Einsatz war die Selbstauskunft auf /haushalt/pflicht,
// und dort war sie in 9 von 10 Bereichen ein einfarbiger Streifen, der ohne
// Legende nicht zu entschlüsseln war („kann da schlecht irgendetwas ablesen",
// Tim). Ein Anteilsbalken ohne angeschriebene Teile unterbietet Regel 1 —
// wer die Form wieder braucht, nimmt die große mit `legende`.
