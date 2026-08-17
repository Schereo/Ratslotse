"use client";

// <Gegenbalken> — ein oder zwei 100-%-Leisten auf EINER Basis (GB-04).
//
// Der Maßstabsfehler aus Runde 1 (zwei Balken, jeder für sich „100 %", und
// schon sah ein Defizit-Haushalt ausgeglichen aus) ist hier Typsystem:
// `basis` ist EIN Wert für alle Zeilen. Asymmetrische 100 % sind nicht
// konstruierbar — eine Zeile, deren Segmente die Basis nicht erreichen,
// endet sichtbar früher, und die Lücke bekommt mit `restLabel` einen Namen
// („aus dem Ersparten", Schraffur + Signal-Kante, Differenz-Konvention).
//
// BESCHRIFTUNG (GB-04 wörtlich): Ein Segment unter 10 % der Basis trägt
// seinen Text nie im Balken — er steht außerhalb, in der Legende. Die steht
// hier IMMER unter dem Balken (H4-A Mobil-Regel „komplette Legende unterm
// Balken", und auch am Desktop ist sie die Zeile, die vorgelesen wird).
// Text IM Balken ist Zusatz, kein Ersatz — und opt-in je Zeile
// (`imBalken`), weil er nur auf Segmenten trägt, deren Farbe gegen
// `--hh-seg-text` 4,5 : 1 hält (DESIGNSPRACHE § 4, Tafel-Regel). Gemessen
// wird er im unsichtbaren Zwilling (`SegmentText`): nie verkleinert, nie
// abgeschnitten — eine gekappte 169,2 liest sich als 16.
//
// FARBEN: nur Rampen-Token. Ohne eigene Angabe verteilt die Zeile ihre
// Rampe (`--hh-ein-*` bzw. `--hh-aus-*`) über die Segmente, dunkel nach
// hell in der übergebenen Reihenfolge. Signal-Orange gibt es hier genau
// einmal: am Rest und an der Marke — Differenzen, keine Bewertungen.
//
// MATHE: pure Prozentrechnung. Keine d3-Abhängigkeit — die Form ist die
// redaktionelle Aussage, nicht die Geometrie (Entscheidungsregel GB-15).

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";

export type GegenbalkenSegment = {
  label: string;
  /** In derselben Einheit wie `basis`. */
  wert: number;
  /** Rampen-Token; ohne Angabe verteilt die Zeile ihre Rampe. */
  farbe?: string;
  /** Schraffiert statt gefüllt — „keine Angabe" (Lücken-Konvention). */
  offen?: boolean;
  /** Kurzform für den Balken, wenn der volle Name nicht passt. */
  kurz?: string;
};

export type GegenbalkenZeile = {
  /** „Wo das Geld eingeht" — steht über der Leiste, mit der Zeilensumme. */
  titel: string;
  segmente: GegenbalkenSegment[];
  /** Welche Rampe die Vorgabefarben stellt. Vorgabe: `aus`. */
  rampe?: "ein" | "aus";
  /** Text im Balken (gemessen, ab 10 % der Basis). Nur einschalten, wenn
   *  die Segmentfarben gegen `--hh-seg-text` tragen (Tafel-Kontext). */
  imBalken?: boolean;
};

/** Letzte nutzbare Stufe je Rampe — dahinter ist die Rampe zu blass für
 *  freistehende Flächen (dieselben Grenzen wie im Haushalts-Gegenbalken). */
const LETZTE_STUFE = { ein: 6, aus: 9 } as const;

/** Unter diesem Anteil der Basis steht die Beschriftung außerhalb (GB-04). */
const MINDEST_ANTEIL = 0.1;

/** Beschriftungsregel wörtlich aus H-03: Ein Segment trägt seinen Text nur,
 *  wenn er WIRKLICH hineinpasst — gemessen im unsichtbaren Zwilling, nicht
 *  geschätzt. Der Reihe nach probiert: „Name · Wert", „Kurzname · Wert",
 *  Kurzname, nichts. Nie verkleinern, nie abschneiden.
 *
 *  Der sichtbare Text bleibt während der Messung stehen, und der State wird
 *  nur gesetzt, wenn sich das Ergebnis ändert — sonst stößt jeder Wechsel
 *  den ResizeObserver erneut an (Dauerflackern, Tim 16.08.). Nach dem
 *  Font-Swap wird noch einmal gemessen: Die Elementbreite ändert sich dabei
 *  nicht, der Observer schlüge also nie an. */
export function SegmentText({ stufen }: { stufen: string[] }) {
  const box = useRef<HTMLSpanElement>(null);
  const mess = useRef<HTMLSpanElement>(null);
  const [text, setText] = useState("");
  // Zu EINEM String serialisiert, damit der Effekt eine stabile Abhängigkeit
  // hat — ein Array wäre bei jedem Render ein neues Objekt. JSON statt eines
  // Trennzeichens, weil die Kandidaten selbst Mittelpunkte und Kommata tragen.
  const schluessel = JSON.stringify(stufen);

  useLayoutEffect(() => {
    const el = box.current, m = mess.current;
    if (!el || !m) return;
    const kandidaten = JSON.parse(schluessel) as string[];
    const entscheide = () => {
      // clientWidth SCHLIESST das Padding ein, der Zwilling misst nur den
      // Text — ohne Abzug hielten wir einen Namen für passend, obwohl die
      // 16 px Innenabstand fehlten und er doch überlief.
      const stil = getComputedStyle(el);
      const platz = el.clientWidth
        - parseFloat(stil.paddingLeft || "0") - parseFloat(stil.paddingRight || "0");
      let passend = "";
      for (const k of kandidaten) {
        m.textContent = k;
        if (m.scrollWidth <= platz) { passend = k; break; }
      }
      m.textContent = "";
      setText((alt) => (alt === passend ? alt : passend));
    };
    entscheide();
    const ro = new ResizeObserver(entscheide);
    ro.observe(el);
    let lebt = true;
    document.fonts?.ready.then(() => { if (lebt) entscheide(); });
    return () => { lebt = false; ro.disconnect(); };
  }, [schluessel]);

  return (
    <span ref={box} className="relative block w-full overflow-hidden whitespace-nowrap px-2">
      {text}
      <span ref={mess} aria-hidden="true" className="pointer-events-none invisible absolute left-0 top-0 whitespace-nowrap" />
    </span>
  );
}

function farbeVon(s: GegenbalkenSegment, i: number, rampe: "ein" | "aus"): string {
  return s.farbe ?? `var(--hh-${rampe}-${Math.min(i, LETZTE_STUFE[rampe])})`;
}

function schraffur(farbe: string): string {
  return `repeating-linear-gradient(45deg, ${farbe} 0 3px, transparent 3px 6px)`;
}

function Leiste({ zeile, basis, nachkomma, restLabel, marke }: {
  zeile: GegenbalkenZeile; basis: number; nachkomma: number; restLabel?: string;
  marke?: { wert: number; label: string };
}) {
  const rampe = zeile.rampe ?? "aus";
  const gezeigt = zeile.segmente.filter((s) => s.wert > 0);
  const summe = gezeigt.reduce((n, s) => n + s.wert, 0);
  // Die Lücke zur Basis. Unterhalb eines halben Anzeigeschritts ist sie
  // Rundungsrauschen, kein Rest.
  const epsilon = 0.5 / 10 ** nachkomma;
  const rest = basis - summe > epsilon ? basis - summe : null;

  const beschreibung = [
    ...gezeigt.map((s) => `${s.label} ${deZahl(s.wert, nachkomma)}`),
    ...(rest != null && restLabel ? [`${restLabel} ${deZahl(rest, nachkomma)}`] : []),
  ].join(", ");

  // Die Zeilensumme steht nur an, wenn sie eine eigene Auskunft ist: Bei
  // einer vollen Zeile weicht sie von der Basis höchstens um Rundungsreste
  // der Segmente ab („883,8" unter einer Basis von 883,9) — zwei fast
  // gleiche Zahlen übereinander wären eine Frage, keine Antwort.
  const zeigeSumme = rest != null || summe - basis > epsilon;

  return (
    <div>
      <p className="mb-1.5 text-[12.5px] font-semibold">
        {zeile.titel}
        {zeigeSumme && (
          <span className="font-normal text-muted-foreground"> — {deZahl(summe, nachkomma)}</span>
        )}
      </p>
      <div
        role="img"
        aria-label={`${zeile.titel}: ${beschreibung}`}
        // `relative` trägt die Marke; sie sitzt über dem Balken und wird
        // deshalb nicht vom `overflow-hidden` des Innenkastens beschnitten.
        className="relative flex h-7 rounded-md bg-muted"
      >
        {marke && marke.wert > 0 && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 z-10 w-0.5 -translate-x-1/2 bg-signal"
            style={{ left: `${Math.min((marke.wert / basis) * 100, 100)}%` }}
          />
        )}
        <div className="flex h-full gap-[1.5px] overflow-hidden rounded-md" style={{ width: `${Math.min((summe / basis) * 100, 100)}%` }}>
          {gezeigt.map((s, i) => {
            const farbe = farbeVon(s, i, rampe);
            return (
              <span
                key={`${s.label}-${i}`}
                className="flex min-w-0 items-center overflow-hidden text-[11px] font-semibold"
                // Breite relativ zur SUMME der Zeile, weil der äußere Kasten
                // schon den Anteil an der Basis trägt — so bleiben beide
                // Maßstäbe exakt, ohne Mindestbreiten.
                style={{
                  width: `${(s.wert / summe) * 100}%`,
                  background: s.offen ? schraffur(farbe) : farbe,
                  color: "var(--hh-seg-text)",
                }}
              >
                {zeile.imBalken && !s.offen && s.wert / basis >= MINDEST_ANTEIL && (
                  <SegmentText stufen={[
                    `${s.label} · ${deZahl(s.wert, nachkomma)}`,
                    ...(s.kurz ? [`${s.kurz} · ${deZahl(s.wert, nachkomma)}`, s.kurz] : []),
                  ]} />
                )}
              </span>
            );
          })}
        </div>
        {rest != null && restLabel && (
          <span
            className="hh-schraffur ml-[1.5px] h-full rounded-r-md border border-dashed border-signal"
            style={{ width: `${(rest / basis) * 100}%` }}
          />
        )}
      </div>
      {/* Die Legende ist die verbindliche Beschriftung — Text im Balken ist
          Zusatz. Segmente unter 10 % stehen NUR hier (GB-04). */}
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
        {gezeigt.map((s, i) => {
          const farbe = farbeVon(s, i, rampe);
          return (
            <span key={`${s.label}-${i}`} className="inline-flex items-center gap-1.5 text-[11px] text-foreground/80">
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-[2px]"
                style={{ background: s.offen ? schraffur(farbe) : farbe }}
              />
              {s.label} <span className="tabular-nums">{deZahl(s.wert, nachkomma)}</span>
            </span>
          );
        })}
        {rest != null && restLabel && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-signal">
            <span aria-hidden="true" className="hh-schraffur h-2 w-2 rounded-[2px] border border-dashed border-signal" />
            {restLabel} <span className="tabular-nums">{deZahl(rest, nachkomma)}</span>
          </span>
        )}
      </div>
    </div>
  );
}

export function Gegenbalken({
  zeilen, basis, einheit = "Mio. €", nachkomma = 1, restLabel, marke, beleg, className,
}: {
  /** Eine oder zwei Leisten — mehr wären keine Gegenüberstellung mehr. */
  zeilen: GegenbalkenZeile[];
  /** EIN Wert für alle Zeilen = 100 %. Üblicherweise die größere der beiden
   *  Summen — nie je Zeile die eigene. */
  basis: number;
  /** Steht als Mono-Zeile rechts über den Leisten. */
  einheit?: string;
  /** Feste Nachkommastellen aller Beträge. */
  nachkomma?: number;
  /** Name der Lücke zwischen kürzerer Zeile und Basis („aus dem
   *  Ersparten") — ohne ihn bleibt die Lücke leere Spur. */
  restLabel?: string;
  /** Ein beschrifteter Signal-Strich quer über der ersten Leiste — „hier
   *  ist die Differenz", nie eine Bewertung. */
  marke?: { wert: number; label: string };
  /** Beleg-Chip-Slot (GB-00). */
  beleg?: ReactNode;
  className?: string;
}) {
  const gezeigt = zeilen.filter((z) => z.segmente.some((s) => s.wert > 0));
  if (!gezeigt.length || !(basis > 0)) return null;

  return (
    <div className={className}>
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
          {gezeigt.length > 1 ? "Eine Basis für beide Leisten: " : "Basis: "}
          {deZahl(basis, nachkomma)} {einheit} = 100&nbsp;%{beleg}
        </span>
      </div>
      <div className="flex flex-col gap-3.5">
        {gezeigt.map((z, i) => (
          <Leiste key={z.titel} zeile={z} basis={basis} nachkomma={nachkomma}
            restLabel={restLabel} marke={i === 0 ? marke : undefined} />
        ))}
      </div>
      {marke && marke.wert > 0 && (
        <p className="mt-2 flex items-start gap-1.5 text-[11.5px] leading-snug text-signal">
          <span aria-hidden="true" className="mt-[3px] h-3 w-0.5 flex-none bg-signal" />
          <span>{marke.label}</span>
        </p>
      )}
    </div>
  );
}
