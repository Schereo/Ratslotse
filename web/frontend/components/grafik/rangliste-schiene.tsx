"use client";

// <RanglisteSchiene> — eine sortierte Liste mit sichtbarer Schiene (GB-03).
//
// Die Schiene ist der Unterschied zum nackten Balken: Sie zeigt, dass die
// Skala bei null anfängt und wo ihr Ende liegt — ohne sie schwebten die
// Balken, und ein abgeschnittener Nullpunkt machte aus 1.974 gegen 1.651
// optisch einen Faktor drei. Wer die Unterschiede größer zeigen will, als
// sie sind, hat den Zweck einer Rangliste verfehlt.
//
// HERVORHEBEN JA, BEWERTEN NIE: `hervorgehoben` färbt eine Zeile dunkler,
// damit man die eigene Stadt (oder den Suchtreffer) findet — nicht, damit man
// sie bewertet. Eine Grün/Rot-Prop existiert nicht und bekommt diese
// Komponente auch nie (GB-03: „keine Bewertungsfarben", die Regel des ganzen
// Bereichs, s. components/grafik/hantel.tsx).
//
// Mobil (H4-A, eingebaut, kein Prop): Unter 480 px Containerbreite wandert
// das Label ÜBER den Balken, die Schiene nimmt die volle Breite, der Wert
// bleibt am Balkenende.

import type { ReactNode } from "react";
import { deZahl } from "@/components/grafik/format";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type RanglisteZeile = {
  label: string;
  wert: number;
  /** Dunkler zeichnen, damit man die Zeile findet — keine Bewertung. */
  hervorgehoben?: boolean;
  /** Eine Zusatzzeile unter dem Balken („Stadtentwicklung · 8 Jahrgänge"). */
  zusatz?: ReactNode;
};

export function RanglisteSchiene({
  zeilen, schiene = "null-bis-max", einheit, nachkomma = 0, mittelmarke, beleg,
}: {
  zeilen: RanglisteZeile[];
  /** `"null-bis-max"` (Default) oder ein festes Paar `[min, max]` — die
   *  Null-Basis ist die Voreinstellung, kein Sonderfall. */
  schiene?: "null-bis-max" | [number, number];
  /** Steht hinter jedem Wert: „%", „€", „Mio. €". */
  einheit: string;
  nachkomma?: number;
  /** Eine beschriftete Marke auf der Schiene, z. B. der Mittelwert. */
  mittelmarke?: { wert: number; label: string };
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: ReactNode;
}) {
  const { box, breite } = useBreite();
  const schmal = breite < 480;
  if (!zeilen.length) return null;

  const [von, bis] = schiene === "null-bis-max"
    ? [0, Math.max(...zeilen.map((z) => z.wert), 0)]
    : schiene;
  const spanne = bis - von || 1;
  const anteil = (w: number) => Math.min(Math.max(((w - von) / spanne) * 100, 0), 100);

  const balken = (z: RanglisteZeile) => (
    <span
      aria-hidden="true"
      className="relative block h-1.5 w-full overflow-hidden rounded-full"
      style={{ background: "var(--hh-ein-6)" }}
    >
      <span
        className="block h-full rounded-full"
        style={{
          width: `${Math.max(anteil(z.wert), 1.5)}%`,
          background: z.hervorgehoben ? "var(--hh-ein-0)" : "var(--hh-ein-3)",
        }}
      />
      {mittelmarke && (
        <span
          className="absolute inset-y-0 w-px bg-foreground/50"
          style={{ left: `${anteil(mittelmarke.wert)}%` }}
        />
      )}
    </span>
  );

  const wertText = (z: RanglisteZeile) => (
    <span className={cn(
      "whitespace-nowrap text-right font-mono text-[12px] tabular-nums",
      z.hervorgehoben ? "font-bold text-foreground" : "text-muted-foreground",
    )}>
      {deZahl(z.wert, nachkomma)}&nbsp;{einheit}
    </span>
  );

  return (
    <div ref={box}>
      <ol className={cn("flex flex-col", schmal ? "gap-2.5" : "gap-1.5")}>
        {zeilen.map((z) => (
          <li key={z.label} className="flex flex-col gap-0.5">
            {schmal ? (
              // Label ÜBER den Balken (H4-A) — der Wert bleibt am Balkenende.
              <>
                <span className={cn(
                  "text-[12.5px] leading-tight",
                  z.hervorgehoben ? "font-bold" : "text-foreground/85",
                )}>
                  {z.label}
                </span>
                <span className="flex items-center gap-2">
                  {balken(z)}
                  {wertText(z)}
                </span>
              </>
            ) : (
              <span className="grid grid-cols-[minmax(7.5rem,11rem)_1fr_auto] items-center gap-3">
                <span className={cn(
                  "truncate text-[12.5px] leading-tight",
                  z.hervorgehoben ? "font-bold text-foreground" : "text-muted-foreground",
                )}>
                  {z.label}
                </span>
                {balken(z)}
                {wertText(z)}
              </span>
            )}
            {z.zusatz && (
              <span className="text-[10.5px] leading-snug text-muted-foreground">
                {z.zusatz}
              </span>
            )}
          </li>
        ))}
      </ol>
      {(mittelmarke || beleg) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-muted-foreground">
          {mittelmarke && (
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2.5 w-px bg-foreground/50" />
              {mittelmarke.label}: {deZahl(mittelmarke.wert, nachkomma)}&nbsp;{einheit}
            </span>
          )}
          {beleg}
        </p>
      )}
    </div>
  );
}
