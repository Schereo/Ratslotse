"use client";

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/** Der KI-Funke an einem automatisch erstellten Text (Tims Wunsch
 *  12.11.2026): statt einer Hinweiszeile darüber ein kleiner orangefarbener
 *  Stern direkt am Text, der beim Überfahren — auf dem Telefon beim Antippen —
 *  sagt, woher der Text kommt und was verbindlich ist.
 *
 *  Ein Knopf, damit er per Tastatur und Tippen erreichbar ist; die Erklärung
 *  steht zugleich als `aria-label` da, ein Bildschirmleser braucht die Karte
 *  also nicht. */
export function KiStern({ text = "Automatisch aus den Unterlagen erstellt. Verbindlich sind die Unterlagen im Ratsinfo.", className }: {
  text?: string;
  className?: string;
}) {
  return (
    <span className={cn("group/ki relative inline-flex align-[-0.15em]", className)}>
      <button type="button" aria-label={text}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
        className="relative z-[2] inline-flex h-5 w-5 items-center justify-center rounded-full text-signal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <Sparkles className="h-3.5 w-3.5" aria-hidden />
      </button>
      <span role="tooltip" aria-hidden
        className={cn(
          "pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 w-max max-w-[min(16rem,70vw)] -translate-x-1/2 rounded-lg border border-border bg-popover px-2.5 py-1.5",
          "text-left text-xs font-normal leading-snug text-popover-foreground shadow-lg",
          "invisible opacity-0 transition-[opacity,visibility] duration-tipp ease-out-strong",
          "maus:group-hover/ki:visible maus:group-hover/ki:opacity-100 group-focus-within/ki:visible group-focus-within/ki:opacity-100",
        )}>
        {text}
      </span>
    </span>
  );
}
