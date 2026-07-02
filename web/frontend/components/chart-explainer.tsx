"use client";

import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { Mascot } from "@/components/mascot";

/**
 * „Was zeigt mir das?" — aufklappbare Lotti-Erklärung unter Chart-Überschriften.
 * Charts ohne Einordnung sind die größte Hürde für Nicht-Datenmenschen; hier
 * erklärt Lotti Lesart und Grenzen der Darstellung in zwei, drei Sätzen.
 */
export function ChartExplainer({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:underline"
      >
        <HelpCircle className="h-3.5 w-3.5" /> Was zeigt mir das?
      </button>
      {open && (
        <div className="mt-2 flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/5 p-3">
          <Mascot pose="point" className="h-11 w-11 shrink-0" />
          <div className="text-xs leading-relaxed text-foreground/90">{children}</div>
        </div>
      )}
    </div>
  );
}
