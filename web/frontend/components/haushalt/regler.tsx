"use client";

// Regler des Haushalts-Labors (Design H-19, zweite Runde).
//
// Der native Range-Input war „irgendein Slider mit irgendeiner Zahl" (Tim,
// 16.08.): keine Skala, kein Bezugspunkt, keine sichtbare Wirkung. Hier
// bekommt er drei Dinge, die genau das beheben:
//
//  1. eine **Ist-Marke** auf der Bahn — wo steht die Stadt heute,
//  2. **Anschläge mit Beschriftung** — was ist überhaupt der Rahmen,
//  3. eine **Wirkungszeile** direkt darunter — was macht dieser eine Regler.
//
// Der Input bleibt ein echtes <input type="range">: Tastatur, Screenreader
// und Touch-Verhalten kommen so vom Browser. Sichtbar ist nur der Griff
// (`.hh-regler` in globals.css), Bahn und Marken liegen als Divs darunter.

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Regler({
  id, label, value, min, max, step, onChange,
  anzeige, ist, marken, wirkung, geaendert,
}: {
  id: string;
  label: ReactNode;
  value: number;
  min: number; max: number; step: number;
  onChange: (v: number) => void;
  /** Der Wert rechts neben dem Titel — schon fertig formatiert. */
  anzeige: ReactNode;
  /** Wo steht die Stadt heute? (Wert auf der Skala, meist 0.) */
  ist?: { value: number; label: string };
  /** Beschriftung der beiden Anschläge. */
  marken?: { min: string; max: string };
  /** Was bewirkt dieser Regler gerade? */
  wirkung?: ReactNode;
  geaendert: boolean;
}) {
  const anteil = (v: number) => ((v - min) / (max - min)) * 100;
  // Die Füllung läuft von der Ist-Marke zum aktuellen Wert — so zeigt der
  // Balken die Änderung, nicht den absoluten Wert.
  const von = Math.min(anteil(ist?.value ?? min), anteil(value));
  const bis = Math.max(anteil(ist?.value ?? min), anteil(value));

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <label htmlFor={id} className="text-[13px] font-semibold">{label}</label>
        <span className="font-mono text-[13px] tabular-nums">{anzeige}</span>
      </div>

      <div className="relative mt-2.5 h-6">
        {/* Bahn */}
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-muted" />
        {/* Füllung ab der Ist-Marke */}
        <div
          className={cn("pointer-events-none absolute top-1/2 h-2 -translate-y-1/2 rounded-full",
            geaendert ? "bg-primary" : "bg-transparent")}
          style={{ left: `${von}%`, width: `${bis - von}%` }}
        />
        {/* Ist-Marke: der Bezugspunkt, der vorher fehlte */}
        {ist && (
          <div aria-hidden className="pointer-events-none absolute top-1/2 h-4 w-[2px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/35"
            style={{ left: `${anteil(ist.value)}%` }} />
        )}
        <input
          id={id} type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="hh-regler absolute inset-0 h-6 w-full"
        />
      </div>

      {(marken || ist) && (
        <div className="relative mt-0.5 h-[13px]">
          {marken && (
            <>
              <span className="absolute left-0 font-mono text-[10px] text-muted-foreground">{marken.min}</span>
              <span className="absolute right-0 font-mono text-[10px] text-muted-foreground">{marken.max}</span>
            </>
          )}
          {ist && (
            <span aria-hidden
              className="absolute -translate-x-1/2 whitespace-nowrap font-mono text-[10px] text-foreground/55"
              style={{ left: `${anteil(ist.value)}%` }}>
              {ist.label}
            </span>
          )}
        </div>
      )}

      {wirkung && (
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{wirkung}</p>
      )}
    </div>
  );
}
