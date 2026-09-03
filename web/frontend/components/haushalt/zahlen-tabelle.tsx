"use client";

// Die Zahlentabelle des Haushalts-Ressorts — Tims Befund vom 26.08.2026 an
// „Was in den Listen stand": „Ertrag und Aufwand sind je nachdem, ob die
// Felder befüllt sind, immer ein bisschen verrückt […] sehr schwer erkennbar,
// wo was zugehört."
//
// Die Wurzel war die Bauform: Jede Zeile war ihr EIGENES CSS-Grid mit
// auto-Spalten — die Grenze zwischen Ertrag und Aufwand wurde je Zeile neu
// berechnet und wanderte mit der Füllung. Deshalb hier eine echte <table>:
// ein Spaltenraster für alle Zeilen, und dazu die drei Dinge, die eine
// Zahlentabelle lesbar machen:
//
// - **Spaltenlinien** vor jeder Zahlenspalte — auf einen Blick klar, in
//   welcher Spalte eine Zahl steht, auch wenn die Nachbarzelle leer ist.
// - **Klebender Kopf**: Bei langen Listen scrollt die Beschriftung mit,
//   direkt unter dem Abschnitts-Streifen der Seite. Darum `border-separate`
//   statt `border-collapse` — kollabierte Rahmen kleben in Chrome nicht am
//   Kopf fest — und ein OPAKER Kopf-Hintergrund (bg-card), damit die Zeilen
//   darunter durchscrollen statt durchzuscheinen. Wichtig für Nachbauten:
//   Kein `overflow-hidden` auf einem Vorfahren, das erdet jedes sticky.
// - **Vorzeichen tragen Farbe**: Plus grün, Minus Signal-Orange — dieselben
//   Token wie überall im Frontend (decision-ui, zeitreihe). Die Farbe
//   kodiert die RICHTUNG der Änderung, kein Urteil: Auch ein grünes Plus
//   beim Aufwand heißt nur „mehr", nicht „gut".
//
// Bewusst Bausteine (Tabelle + Zellen) statt einer Daten-Prop: Die erste
// Spalte trägt je Verwendung anderes (Name + THH + Erläuterungstext), das
// soll JSX bleiben. Wer die nächste Zahlentabelle im Ressort baut, baut sie
// hieraus — nicht als neues Grid daneben.
//
// ERST AB `breit` IST SIE EINE TABELLE (30.08.2026), darunter eine Liste.
// Drei Spalten aus Text und Zahlen haben eine Mindestbreite, die sich nicht
// wegformatieren lässt: gemessen 400 px bei 283 px Platz — die Seite lief auf
// dem Telefon waagerecht über (`scrollWidth` 480 statt 375, die Messung, die
// für den ganzen Bereich gilt). Ein `overflow-x`-Container wäre der billige
// Weg gewesen, kostet aber genau das Kleben des Kopfes: Ein scrollender
// Vorfahre wird zum Bezugsrahmen jedes `sticky`, und `overflow-x: auto` zieht
// `overflow-y` zwangsweise mit.
//
// Deshalb dieselbe Grammatik wie sonst im Ressort — die Kachelfläche wird auf
// dem Telefon zur Rangliste, der Zeitstrahl kippt senkrecht: Der Kopf
// verschwindet, jede Zeile wird ein Block, und die Beträge tragen ihre
// Spaltenbeschriftung selbst mit sich. Der klebende Kopf wird damit
// entbehrlich, statt zu fehlen: Was er beschriftet hätte, steht an der Zahl.
//
// Die Schwelle ist `breit` (≥ 1024 px) und NICHT `mobil` (< 744 px), obwohl
// im Bereich sonst dort gestapelt wird. Gemessen: Bei 744 px fehlten immer
// noch 8 px (`scrollWidth` 752) — die Mindestbreite der Tabelle liegt nun
// einmal darüber, und eine Schwelle, die knapp nicht reicht, ist keine.
// Zwischen 744 und 1024 gibt es keinen benannten Screen; ihn dafür zu
// erfinden hieße, die Design-Schwellen um eine Tabelle herum zu bauen.
// `breit` ist reine Breite und gilt auf dem iPad quer genauso — genau die
// Frage, um die es hier geht.

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Wo der Tabellenkopf klebt: direkt unter dem, was auf dem jeweiligen
 *  Gerät oben klebt. Ab `desk` ist das der Abschnitts-Streifen
 *  (abschnitte.tsx: py-2 + Chips + border-b — im Browser gemessen: 49 px).
 *  Darunter kleben ZWEI Dinge übereinander: der App-Header (layout.tsx,
 *  gemessen 61 px ohne Notch, wächst mit `env(safe-area-inset-top)`) und
 *  darunter angedockt der Abschnitts-Streifen — zusammen 110 px plus
 *  Sicherheitszone. Wer Streifen oder Header umbaut, misst hier nach und
 *  zieht abschnitte.tsx (ANKER_KLASSE) mit. */
const KLEBE_AB = "top-[calc(env(safe-area-inset-top)+110px)] desk:top-[49px]";

export function ZahlenTabelle({ spalten, fuss, children, className }: {
  spalten: { title: string; zahl?: boolean }[];
  /** Optionale Summenzeile(n) als <tr> — sie ankern die Spalten am Fuß. */
  fuss?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-border/60", className)}>
      <table className="w-full border-separate border-spacing-0 text-[12px] leading-snug">
        {/* Der Kopf beschriftet die Spalten — unterhalb von `breit` gibt es
            keine, dort tragen die Beträge ihre Beschriftung selbst
            (s. `BetragZelle`). */}
        <thead className="hidden breit:table-header-group">
          <tr>
            {spalten.map((s, i) => (
              <th
                key={s.title}
                scope="col"
                className={cn(
                  "sticky z-[5] border-b border-border/60 bg-card px-3 py-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground",
                  KLEBE_AB,
                  i === 0 && "rounded-tl-xl",
                  i === spalten.length - 1 && "rounded-tr-xl",
                  s.zahl ? "border-l border-l-border/50 text-right" : "text-left",
                )}
              >
                {s.title}
              </th>
            ))}
          </tr>
        </thead>
        {/* Gestapelt wird jede Zeile ein Block. Die Trennlinie wandert dabei
            von der Zelle auf die Zeile — sonst zöge jede der drei Zellen
            ihren eigenen Strich quer durch den Block. */}
        <tbody className="[&>tr]:block [&>tr]:border-t [&>tr]:border-border/40 [&>tr]:py-1 [&>tr:first-child]:border-t-0 [&>tr>td]:border-t-0 breit:[&>tr]:table-row breit:[&>tr]:border-t-0 breit:[&>tr]:py-0 breit:[&>tr>td]:border-t breit:[&>tr:first-child>td]:border-t-0">
          {children}
        </tbody>
        {fuss && (
          <tfoot className="[&>tr]:block [&>tr]:border-t [&>tr]:border-border/60 [&>tr]:py-1 [&>tr>td]:border-t-0 breit:[&>tr]:table-row breit:[&>tr]:border-t-0 breit:[&>tr]:py-0 breit:[&>tr>td]:border-t">
            {fuss}
          </tfoot>
        )}
      </table>
    </div>
  );
}

/** Erste Spalte einer Zeile: freier Inhalt (Name, Kennungen, Erklärtext). */
export function TextZelle({ children, className }: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <td className={cn("block border-border/40 px-3 py-1.5 align-baseline breit:table-cell",
      className)}>
      {children}
    </td>
  );
}

/** Eine Zahlenzelle: rechtsbündig, mono, mit Spaltenlinie — und das
 *  Vorzeichen als Farbe. `euro` steuert nur die Farbe; was dasteht, liefert
 *  `text` (die Formate unterscheiden sich je Tabelle).
 *
 *  `label` ist die Beschriftung ihrer Spalte. Gestapelt gibt es keinen
 *  Tabellenkopf mehr (s. Modulkopf), und eine nackte Zahl unter einem
 *  Fließtext sagt nicht, ob sie Ertrag oder Aufwand ist — dort steht das
 *  Label deshalb vor dem Betrag. Ohne `label` bleibt die Zelle auf schmalen
 *  Schirmen unbeschriftet; wer eine neue Zahlentabelle baut, gibt es mit. */
export function BetragZelle({ euro, text, label, className }: {
  euro: number | null;
  text: string;
  label?: string;
  className?: string;
}) {
  return (
    <td
      className={cn(
        "whitespace-nowrap border-l-border/40 border-t-border/40 px-3 text-right align-baseline font-mono text-[11.5px] tabular-nums",
        // Gestapelt: volle Breite, Label links, Betrag rechts — und keine
        // Spaltenlinie, die dort nichts mehr trennt.
        "flex items-baseline justify-between gap-3 py-0.5",
        "breit:table-cell breit:border-l breit:py-1.5",
        // Ohne Betrag entfällt die Zeile — gestapelt gibt es keine Spalte, die
        // gefüllt werden müsste. In der Tabelle muss die Zelle ihr „—" zeigen
        // (die Spalte steht ja da); in der Liste sagt das Weglassen dasselbe,
        // ohne unter jeder Position eine tote Zeile zu hinterlassen. Trägt
        // eine Position in BEIDEN Spalten nichts, steht sie nur mit ihrem
        // Text da — und genau so steht sie auch im Dokument.
        euro == null && "hidden breit:table-cell",
        euro == null
          ? "text-muted-foreground/60"
          : euro < 0
            ? "text-signal"
            : "text-emerald-700 dark:text-emerald-400",
        className,
      )}
    >
      {label && (
        <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground breit:hidden">
          {label}
        </span>
      )}
      <span>{text}</span>
    </td>
  );
}
