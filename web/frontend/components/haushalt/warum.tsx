"use client";

// Die Begründung der Verwaltung zu einer Plan/Ist-Abweichung, eingeklappt.
//
// Quelle ist Abschnitt 6.3.1 des Jahresabschlusses („Erläuterung der
// erheblichen Plan/Ist-Abweichungen"), der jede Abweichung ab 20 % gegenüber
// dem Plan begründet. Gezeigt wird der Wortlaut, nicht eine Zusammenfassung:
// Das ist Verwaltungssprache, aber sie ist die Quelle — gekürzt wäre sie
// schnell etwas anderes. Einordnung leisten die Lotti-Kästen daneben.

import { Abweichungsgrund } from "@/lib/haushalt";

export function Warum({ reason, kompakt = false }: {
  reason: Abweichungsgrund | null;
  /** Ohne eigene Überschrift, wenn der Betrag schon darüber steht. */
  kompakt?: boolean;
}) {
  if (!reason) return null;
  return (
    <details className="group ml-0.5 border-l-2 border-border pl-2.5">
      <summary className="cursor-pointer list-none text-[11.5px] font-semibold text-primary marker:content-none">
        <span className="group-open:hidden">
          {kompakt ? "Warum?" : "Warum? — was die Stadt dazu schreibt"}
        </span>
        <span className="hidden group-open:inline">Weniger</span>
      </summary>
      <p className="mt-1.5 max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
        {reason.text}
      </p>
      <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
        Jahresabschluss {reason.year}, Abschnitt 6.3.1 — Wortlaut der Verwaltung
      </p>
    </details>
  );
}
