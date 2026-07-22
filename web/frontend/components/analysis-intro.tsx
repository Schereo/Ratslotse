"use client";

import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** Analyse-Intro (Design 16a①): die Kernaussage steht als EIN Satz offen (mit
 *  der wichtigsten Zahl), die Methodik-Fußnote wandert ins „Wie wird gezählt?"-
 *  Popover. Einheitliches Bauteil für die Parteien-, Personen- und Ziele-
 *  Analyse — der Text bleibt 1:1 erhalten, nur zusammengeklappt. */
export function AnalysisIntro({ summary, children }: { summary: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg bg-primary/5 px-3.5 py-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Info className="h-3.5 w-3.5" />
      </span>
      <p className="min-w-0 flex-1 text-[13px] leading-snug text-foreground">{summary}</p>
      <Popover>
        <PopoverTrigger asChild>
          <button type="button" className="shrink-0 whitespace-nowrap text-xs font-medium text-primary hover:underline">
            Wie wird gezählt?
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 max-w-[calc(100vw-2rem)] text-xs leading-relaxed text-muted-foreground">
          {children}
        </PopoverContent>
      </Popover>
    </div>
  );
}
