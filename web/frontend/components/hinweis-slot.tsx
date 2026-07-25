"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { ChevronDown, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { TOUR_START_EVENT } from "@/components/tour";

export type Hinweis = { key: string; label: string; node: ReactNode };

/**
 * Ein Platz für Hinweise (Design 28a/R4).
 *
 * „Heute" konnte bis zu vier Banner übereinander stapeln — Sitzungspause,
 * Live, Push-Primer, Erste Schritte — und jeder entschied für sich, ob er
 * erscheint. In der Sitzungspause mit frischem Konto schob das den eigentlichen
 * Inhalt unter die Falz: vier Kästen, von denen keiner dringend war.
 *
 * Der Slot zeigt genau den ersten Hinweis, der etwas zu sagen hat. Die
 * Reihenfolge der Liste IST die Priorität (Live > Pause > Erste Schritte >
 * Push) — das Dringlichste zuerst. Was übrig bleibt, wandert in eine Pille und
 * ist einen Tipp entfernt, statt zu verschwinden.
 *
 * Ob ein Hinweis überhaupt etwas rendert, weiß nur er selbst (jeder hängt an
 * eigenen Queries und gibt sonst `null` zurück). Statt diese vier Bedingungen
 * hier zu duplizieren — und bei jeder Änderung nachziehen zu müssen — fragt der
 * Slot das DOM: ein leerer Träger heißt „hat nichts zu sagen". Ein
 * MutationObserver hält das aktuell, wenn eine Query später eintrifft.
 */
export function HinweisSlot({ hinweise, className }: { hinweise: Hinweis[]; className?: string }) {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const [filled, setFilled] = useState<boolean[]>(() => hinweise.map(() => false));
  const [expanded, setExpanded] = useState(false);

  // Absichtlich an der ANZAHL statt am Array: die Liste wird bei jedem Render
  // neu gebaut, ein Array-Dep würde die Observer jedes Mal ab- und neu anmelden.
  const count = hinweise.length;
  useEffect(() => {
    const measure = () =>
      setFilled((prev) => {
        const next = Array.from({ length: count }, (_, i) => (refs.current[i]?.childElementCount ?? 0) > 0);
        return next.some((v, i) => v !== prev[i]) ? next : prev;
      });
    measure();
    const obs = new MutationObserver(measure);
    for (const el of refs.current) if (el) obs.observe(el, { childList: true });
    return () => obs.disconnect();
  }, [count]);

  // Die Tour setzt ihr Spotlight auf echte Elemente und überspringt unsichtbare
  // (offsetParent === null). Ein eingeklappter Hinweis wäre für sie also nicht
  // da — deshalb beim Start alles aufklappen.
  useEffect(() => {
    const open = () => setExpanded(true);
    window.addEventListener(TOUR_START_EVENT, open);
    return () => window.removeEventListener(TOUR_START_EVENT, open);
  }, []);

  const firstIdx = filled.indexOf(true);
  const restIdx = hinweise.map((_, i) => i).filter((i) => filled[i] && i !== firstIdx);

  return (
    // Der Slot besitzt den Abstand, nicht die einzelnen Hinweise: leere und
    // eingeklappte Träger stehen auf display:none und sind damit gar keine
    // Flex-Items mehr — nur zwischen wirklich sichtbaren Hinweisen entsteht Luft.
    <div className={cn("flex flex-col items-start gap-4", className)}>
      {hinweise.map((h, i) => (
        <div
          key={h.key}
          ref={(el) => {
            refs.current[i] = el;
          }}
          className={cn(
            "w-full",
            (!filled[i] || (restIdx.includes(i) && !expanded)) && "hidden",
          )}
        >
          {h.node}
        </div>
      ))}

      {restIdx.length > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((o) => !o)}
          aria-expanded={expanded}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Info className="h-3.5 w-3.5" />
          {expanded
            ? "Weitere Hinweise ausblenden"
            : restIdx.map((i) => hinweise[i].label).join(" · ")}
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")} />
        </button>
      )}
    </div>
  );
}
