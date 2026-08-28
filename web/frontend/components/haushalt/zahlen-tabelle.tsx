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
  spalten: { titel: string; zahl?: boolean }[];
  /** Optionale Summenzeile(n) als <tr> — sie ankern die Spalten am Fuß. */
  fuss?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-border/60", className)}>
      <table className="w-full border-separate border-spacing-0 text-[12px] leading-snug">
        <thead>
          <tr>
            {spalten.map((s, i) => (
              <th
                key={s.titel}
                scope="col"
                className={cn(
                  "sticky z-[5] border-b border-border/60 bg-card px-3 py-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground",
                  KLEBE_AB,
                  i === 0 && "rounded-tl-xl",
                  i === spalten.length - 1 && "rounded-tr-xl",
                  s.zahl ? "border-l border-l-border/50 text-right" : "text-left",
                )}
              >
                {s.titel}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr:first-child>td]:border-t-0">{children}</tbody>
        {fuss && <tfoot>{fuss}</tfoot>}
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
    <td className={cn("border-t border-border/40 px-3 py-1.5 align-baseline", className)}>
      {children}
    </td>
  );
}

/** Eine Zahlenzelle: rechtsbündig, mono, mit Spaltenlinie — und das
 *  Vorzeichen als Farbe. `euro` steuert nur die Farbe; was dasteht, liefert
 *  `text` (die Formate unterscheiden sich je Tabelle). */
export function BetragZelle({ euro, text, className }: {
  euro: number | null;
  text: string;
  className?: string;
}) {
  return (
    <td
      className={cn(
        "whitespace-nowrap border-l border-t border-l-border/40 border-t-border/40 px-3 py-1.5 text-right align-baseline font-mono text-[11.5px] tabular-nums",
        euro == null
          ? "text-muted-foreground/60"
          : euro < 0
            ? "text-signal"
            : "text-emerald-700 dark:text-emerald-400",
        className,
      )}
    >
      {text}
    </td>
  );
}
