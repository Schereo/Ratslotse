"use client";

// <KettenMatrix> — Wiederholungs-Matrix des Grafik-Baukastens (GB-10):
// Feststellung × Jahr, je Zelle die Randmarke des Berichts.
//
// MATHE: pure — hier gibt es nichts zu skalieren, nur zu ordnen.
//
// DER VERTRAG IN VIER REGELN:
//  * Marken-Klartext kommt aus der LEGENDE DER QUELLE (`marken`-Prop) — nie
//    aus dieser Datei. Die Komponente kennt die Buchstaben, die Bedeutung
//    kennt nur der Bericht des jeweiligen Jahrgangs.
//  * Farben sind KATEGORIEN, keine Urteile: B/WB tragen Signal-Orange, weil
//    eine Beanstandung die Abweichungs-Kategorie des Berichts ist; H trägt
//    den Hafenblau-Ton der Rampe, K bleibt neutral. Kein Rot, kein Grün.
//  * Lücken-Jahre rendern in JEDER Zeile — `lueckenJahre` erzwingt die
//    Spalte, eine Seite kann 2024 nicht versehentlich weglassen. Beschriftet
//    werden sie über <LueckenFeld> ÜBER der Matrix (H4-09: „steht als Satz
//    über der Liste auf jedem Gerät"), nie einklappbar.
//  * Mobil (Container < 620 px) kippt die Matrix zur KARTEN-LISTE: je Kette
//    eine Karte mit Chip-Zeile, leere Jahre als leere Slots, das Lücken-Jahr
//    immer als Lücken-Chip. NIE eine horizontal scrollende Matrix (H4-A).
//
// TASTATUR: Ein Tabstopp je Kette (die Zeilen-Überschrift ist ein Button),
// ↑/↓ wechseln die Kette, Enter/Leertaste klappt den Wortlaut auf — dieselbe
// Grammatik wie die Ableseleiste, nur senkrecht. Die Chip-Zeile selbst ist
// Präsentation; ihr Inhalt steht vollständig im `aria-label` der Zeile.

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";
import { LueckenFeld } from "./luecken-feld";

/** Ein belegtes Jahr einer Kette: die Marke, die der Bericht dort setzt. */
export type KettenZelle = { year: number; mark: string };

export type MatrixKette = {
  /** Stabiler Schlüssel (Kettenschlüssel des Backends). */
  key: string;
  titel: string;
  /** Ehrliche Zählangabe unter dem Titel („in 6 von 7 Berichten beanstandet"). */
  untertitel?: string;
  /** Nur belegte Jahre; je Jahr höchstens eine (die schwerste) Marke. */
  zellen: KettenZelle[];
};

export type MatrixLegende = Record<string, { name: string; explanation?: string | null }>;

/** Unter dieser Containerbreite wird aus der Matrix die Karten-Liste:
 *  Zeilen-Label (min. 180 px) + 8 Zellen à ~40 px + Zähler brauchen mehr —
 *  und horizontal scrollen darf die Matrix nie (H4-A). */
const SCHWELLE_KARTEN = 620;

/** B und WB sind die Abweichungs-Kategorie des Berichts (GB-10). */
const ABWEICHUNG = new Set(["B", "WB"]);

function markenFarbe(mark: string): { klasse: string; stil?: React.CSSProperties } {
  if (ABWEICHUNG.has(mark)) return { klasse: "font-bold text-signal" };
  if (mark === "H") return { klasse: "font-semibold", stil: { color: "var(--hh-ein-1)" } };
  return { klasse: "text-muted-foreground" };
}

/** Eine Zelle der Matrix bzw. ein Chip der Karten-Zeile.
 *
 *  `mitJahr` nur in der Karten-Liste: Dort gibt es keine Kopfzeile, der Chip
 *  muss sein Jahr selbst tragen. In der Matrix stünde es doppelt — die
 *  Spaltenköpfe sagen es bereits. */
function Zelle({ year, mark, luecke, mitJahr }: {
  year: number; mark?: string; luecke?: boolean; mitJahr?: boolean;
}) {
  const farbe = mark ? markenFarbe(mark) : null;
  return (
    <div
      aria-hidden="true"
      className={cn(
        "flex flex-none flex-col items-center justify-center rounded-lg border",
        mitJahr ? "h-[42px] w-[34px]" : "h-[36px] w-[36px]",
        luecke
          ? "hh-schraffur border-dashed border-signal/70"
          : mark
            ? ABWEICHUNG.has(mark) ? "border-signal/45 bg-card" : "border-border bg-card"
            : "border-dashed border-border/70",
      )}
    >
      <span className={cn("font-mono leading-none", mitJahr ? "text-[10.5px]" : "text-[11.5px]", farbe?.klasse)}
        style={farbe?.stil}>
        {luecke ? "" : mark ?? "·"}
      </span>
      {mitJahr && (
        <span className={cn(
          "mt-1 font-mono text-[8.5px] leading-none",
          luecke ? "font-semibold text-signal" : "text-muted-foreground",
        )}>
          {String(year).slice(-2)}
        </span>
      )}
    </div>
  );
}

export function KettenMatrix({ ketten, years, lueckenJahre, marken, detail, beleg, className }: {
  ketten: MatrixKette[];
  /** Jahrgänge MIT Bericht, aufsteigend. */
  years: number[];
  /** Jahrgänge OHNE Bericht — rendern in jeder Zeile als Lücken-Zelle und
   *  über der Matrix als <LueckenFeld> mit Grund. */
  lueckenJahre: { year: number; grund: string; datum?: string }[];
  /** Die Legende der Quelle: Buchstabe → Name (+ Erläuterung). Pflicht —
   *  eine Matrix, die ihre Marken selbst erklärt, würde raten. */
  marken: MatrixLegende;
  /** Aufklappbarer Zeilen-Inhalt (der Wortlaut der Feststellungen). */
  detail?: (kette: MatrixKette) => ReactNode;
  /** Beleg-Chip-Slot (GB-00). */
  beleg?: ReactNode;
  className?: string;
}) {
  const { box, breite } = useBreite();
  const [offen, setOffen] = useState<string | null>(null);
  const zeilenKnoepfe = useRef<(HTMLButtonElement | null)[]>([]);
  const karten = breite < SCHWELLE_KARTEN;

  if (!ketten.length || years.length + lueckenJahre.length === 0) return null;

  const spalten: { year: number; luecke: boolean }[] = [
    ...years.map((year) => ({ year, luecke: false })),
    ...lueckenJahre.map((l) => ({ year: l.year, luecke: true })),
  ].sort((a, b) => a.year - b.year);

  const vorlesen = (k: MatrixKette): string => {
    const teile = spalten.map((s) => {
      if (s.luecke) return `${s.year}: Bericht fehlt`;
      const mark = k.zellen.find((z) => z.year === s.year)?.mark;
      return mark ? `${s.year}: ${marken[mark]?.name ?? mark}` : null;
    }).filter(Boolean);
    return `${k.titel}. ${teile.join(", ")}.`;
  };

  const tasten = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const springe = (ziel: number) => {
      e.preventDefault();
      const j = Math.min(Math.max(ziel, 0), ketten.length - 1);
      zeilenKnoepfe.current[j]?.focus();
    };
    if (e.key === "ArrowDown") springe(i + 1);
    else if (e.key === "ArrowUp") springe(i - 1);
    else if (e.key === "Home") springe(0);
    else if (e.key === "End") springe(ketten.length - 1);
  };

  const zeilenKopf = (k: MatrixKette, i: number) => (
    <button
      type="button"
      ref={(el) => { zeilenKnoepfe.current[i] = el; }}
      onClick={() => setOffen(offen === k.key ? null : k.key)}
      onKeyDown={(e) => tasten(e, i)}
      aria-expanded={offen === k.key}
      aria-label={vorlesen(k)}
      className="min-w-0 rounded-md text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
    >
      <span className="line-clamp-2 font-display text-[14px] font-bold leading-snug tracking-tight">
        {k.titel}
      </span>
      {k.untertitel && (
        <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
          {k.untertitel}
        </span>
      )}
    </button>
  );

  const zaehler = (k: MatrixKette) => (
    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
      {k.zellen.length}×
    </span>
  );

  return (
    <div ref={box} className={cn("min-w-0", className)}>
      {/* Die Lücken-Sätze stehen ÜBER der Matrix, auf jedem Gerät (H4-09) —
          gerendert von der Grafik, nie von der Seite gebastelt (GB-00). */}
      {lueckenJahre.length > 0 && (
        <div className="mb-3 flex flex-col gap-1.5">
          {lueckenJahre.map((l) => (
            <LueckenFeld key={l.year} label={String(l.year)} grund={l.grund} datum={l.datum} />
          ))}
        </div>
      )}

      {karten ? (
        /* Karten-Liste: je Kette eine Karte mit Chip-Zeile (H4-A „Matrix"). */
        <div className="flex flex-col gap-2.5">
          {ketten.map((k, i) => (
            <div key={k.key} className="rounded-xl border border-border bg-card p-3 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                {zeilenKopf(k, i)}
                {zaehler(k)}
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {spalten.map((s) => (
                  <Zelle key={s.year} year={s.year} luecke={s.luecke}
                    mark={k.zellen.find((z) => z.year === s.year)?.mark} mitJahr />
                ))}
              </div>
              {offen === k.key && detail && <div className="mt-3">{detail(k)}</div>}
            </div>
          ))}
        </div>
      ) : (
        /* Matrix: Zeilen-Label + eine Spalte je Jahrgang (Tablet/Desktop). */
        <div
          className="grid items-center gap-x-1.5 gap-y-0"
          style={{
            gridTemplateColumns:
              `minmax(180px, 1fr) repeat(${spalten.length}, minmax(34px, 44px)) auto`,
          }}
        >
          <span className="pb-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Kette
          </span>
          {spalten.map((s) => (
            <span key={s.year} aria-hidden="true"
              className={cn(
                "pb-1.5 text-center font-mono text-[10px]",
                s.luecke ? "font-semibold text-signal" : "text-muted-foreground",
              )}>
              {String(s.year).slice(-2)}
            </span>
          ))}
          <span className="pb-1.5 text-right font-mono text-[9.5px] uppercase text-muted-foreground">
            &nbsp;
          </span>

          {ketten.map((k, i) => (
            <div key={k.key} className="contents">
              <div className="border-t border-border/60 py-2 pr-2">{zeilenKopf(k, i)}</div>
              {spalten.map((s) => (
                <div key={s.year} className="flex justify-center border-t border-border/60 py-2">
                  <Zelle year={s.year} luecke={s.luecke}
                    mark={k.zellen.find((z) => z.year === s.year)?.mark} />
                </div>
              ))}
              <div className="border-t border-border/60 py-2 text-right">{zaehler(k)}</div>
              {offen === k.key && detail && (
                <div className="col-span-full pb-3 pt-1">{detail(k)}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Legende: Buchstaben mit dem Klartext der Quelle — die Erläuterung im
          Wortlaut gehört auf die Seite, hier steht die Zuordnung. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5">
        {Object.entries(marken).map(([mark, m]) => {
          const farbe = markenFarbe(mark);
          return (
            <span key={mark} className="inline-flex items-baseline gap-1.5 text-[11.5px] text-foreground/80">
              <span className={cn("font-mono text-[11px]", farbe.klasse)} style={farbe.stil}>
                {mark}
              </span>
              {m.name}
            </span>
          );
        })}
        {lueckenJahre.length > 0 && (
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
            <span className="hh-schraffur h-3 w-[18px] rounded-[2px] border border-dashed border-signal" />
            Bericht fehlt
          </span>
        )}
        {beleg && <span className="inline-flex items-center text-[11.5px] text-muted-foreground">Quelle{beleg}</span>}
      </div>
    </div>
  );
}
