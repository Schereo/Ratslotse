"use client";

import { useRef, useState } from "react";
import { X } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MELDE_HAEUFIGKEIT, type ProblemFrequency } from "@/lib/probleme";

export type ProblemHelpView = "karte" | "rangliste" | "detail";

const VIEW_COPY: Record<ProblemHelpView, { label: string; article: string; title: string }> = {
  karte: { label: "Karte", article: "die Karte", title: "Karte verstehen" },
  rangliste: { label: "Rangliste", article: "die Rangliste", title: "Rangliste verstehen" },
  detail: { label: "Problem", article: "das Problem", title: "Problem verstehen" },
};
const FREQUENCY_OPTIONS = Object.entries(MELDE_HAEUFIGKEIT) as [ProblemFrequency, string][];

export function ProblemHelp({ view, fictional }: { view: ProblemHelpView; fictional: boolean }) {
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const copy = VIEW_COPY[view];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Lotti-Hilfe ${open ? "schließen" : "öffnen"}: ${copy.label} erklären`}
          aria-expanded={open}
          className="problem-lotti-help group inline-flex min-h-11 items-center gap-2 rounded-xl border border-primary/20 bg-primary/[0.045] py-1 pl-1 pr-3 text-left text-primary shadow-sm transition-[border-color,background-color,transform] hover:border-primary/35 hover:bg-primary/[0.075] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Mascot
            regung={open ? "erklaert" : view === "karte" ? "ruht" : "zeigt-runter"}
            regie="ruhig"
            decorative
            className="problem-lotti-figur h-11 w-11 shrink-0"
          />
          <span>
            <span className="block font-mono text-[9px] font-medium uppercase tracking-[0.11em]">Lotti hilft</span>
            <span className="block text-xs font-semibold text-foreground">{copy.title}</span>
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        ref={contentRef}
        aria-label={`Lotti erklärt ${copy.article}`}
        align="end"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          contentRef.current?.focus();
        }}
        className="max-h-[var(--radix-popover-content-available-height)] w-[22rem] max-w-[calc(100vw-2rem)] overflow-y-auto p-4 text-xs leading-relaxed text-muted-foreground"
      >
        <div className="grid grid-cols-[3rem_1fr_2.75rem] items-start gap-3">
          <Mascot regung="erklaert" regie="ruhig" decorative className="h-12 w-12 shrink-0" />
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">Lotti erklärt</p>
            <p className="mt-1 font-display text-base font-bold text-foreground">{copy.title}</p>
          </div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Hilfe schließen" className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <HelpText view={view} />
        <div className="mt-3"><FrequencyScale /></div>
        <p className="mt-3">Hafenblau zeigt ausschließlich die Zahl unabhängiger Meldungen, von hell nach dunkel. Es ist kein Dringlichkeits- oder Wahrheitsurteil.</p>
        {fictional && (
          <p className="mt-3">
            {view === "detail"
              ? "Dieses Beispiel und seine Zahlen sind frei erfunden. Es zeigt nur, wie eine Detailseite funktioniert."
              : "Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden. Sie zeigen nur, wie die Übersicht funktioniert."}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

function HelpText({ view }: { view: ProblemHelpView }) {
  if (view === "karte") {
    return <p className="mt-3">Die Karte zeigt nur freigegebene, ehrlich kartierbare Orte und Flächen. Stadtweite Probleme und unbrauchbare Geometrien bekommen keinen erfundenen Punkt.</p>;
  }
  if (view === "rangliste") {
    return <p className="mt-3">Die lebenszeitliche Zahl zählt freigegebene unabhängige Meldungen. Aktualisierungen derselben Person erhöhen sie nicht. Rang und Zahl zeigen Aufmerksamkeit, nicht Wahrheit, Dringlichkeit, Schadenshöhe oder die Zahl betroffener Personen.</p>;
  }
  return (
    <>
      <p className="mt-3">Die lebenszeitliche Zahl zählt freigegebene unabhängige Meldungen. Aktualisierungen derselben Person erhöhen sie nicht. Die Seite zeigt nur die moderierte öffentliche Zusammenfassung.</p>
      <p className="mt-3">Stadtweite Probleme und unbrauchbare Geometrien bekommen keinen erfundenen Punkt.</p>
    </>
  );
}

function FrequencyScale() {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5 shadow-sm" aria-label="Hafenblau-Skala der Meldehäufigkeit">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Meldehäufigkeit</span>
        <span className="text-[10px] text-muted-foreground">hell bis dunkel</span>
      </div>
      <div className="mt-2 grid grid-cols-4 gap-1.5">
        {FREQUENCY_OPTIONS.map(([frequency, label]) => (
          <span key={frequency} className="min-w-0 text-center text-[10px] font-medium text-muted-foreground">
            <span className={`frequency-${frequency} block h-2 rounded-full bg-[var(--problem-frequency)]`} aria-hidden />
            <span className="mt-1 block leading-tight">{label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
