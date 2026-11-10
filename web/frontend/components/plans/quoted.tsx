"use client";

// Ein Satz mit seinem Beleg — die kleinste Einheit der Planseite: Was hier
// steht, hat ein Sprachmodell vorgeschlagen, und gezeigt wird es nur, weil die
// wörtliche Stelle in der Quelle steht (council/plan_judge.py). Das Zitat ist
// deshalb nie weiter weg als einen Tipp.

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { cn } from "@/lib/utils";

/** Das Zitat — beim Aufklappen einmal markiert, wie mit einem Textmarker
 *  (`.zitat-marker` in globals.css): Unter dem Text liegt die Markierung, eine
 *  Abdeckung in Kartenfarbe fährt zur Seite weg. Nur `transform`. */
export function Quote({ text, className }: { text: string; className?: string }) {
  const quoted = `„${text}“`;
  return (
    <blockquote className={cn("border-l-2 border-border pl-3 text-[14px] leading-relaxed text-foreground", className)}>
      <span className="zitat-marker">
        <span aria-hidden className="zitat-marker-farbe"><span>{quoted}</span></span>
        <span aria-hidden className="zitat-marker-decke" />
        <span className="relative">{quoted}</span>
      </span>
    </blockquote>
  );
}

/** Ein Satz, darunter auf Tipp die Stelle, die ihn belegt. `tinted`: Die Zeile
 *  steht auf getöntem Grund — dann hat die Abdeckung des Textmarkers nichts zu
 *  verdecken und die Markierung steht sofort. */
export function QuotedLine({ text, quote, label, className, tinted = false }: {
  text: string; quote: string;
  /** Ein kleines Wort davor, das sagt, wessen Auskunft das ist („Laut Bericht“). */
  label?: string;
  className?: string; tinted?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className={className}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-start gap-x-2 rounded-md py-1 text-left hover:bg-primary/[0.03]">
        <span className="min-w-0 break-words text-[14px] leading-snug text-foreground">
          {label && <span className="mr-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">{label}</span>}
          {text}
        </span>
        <span className="mt-0.5 flex items-center gap-1 text-meta text-muted-foreground">
          <span className="hidden sm:inline">Zitat</span>
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
        </span>
      </button>
      <Aufklapp offen={open}>
        <Quote text={quote} className={cn("mb-2 mt-1 text-[13.5px]", tinted && "[&_.zitat-marker-decke]:hidden")} />
      </Aufklapp>
    </div>
  );
}
