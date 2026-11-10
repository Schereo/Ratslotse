"use client";

// Die Sprungleiste der Planseite: „Inhalt · Berichte · Stand · Maßnahmen ·
// Beschlüsse“, mit Zählern, nur was es auf DIESEM Plan gibt. Sie bleibt beim
// Rollen oben stehen — der Klimaschutzplan ist sechs Bildschirme lang, und
// ohne sie weiß man in der Maßnahmenliste nicht mehr, was noch kommt.
//
// Welche Abschnitte es gibt und was gezählt wird, kommt aus
// council/plan_pages.py::sections. Die Markierung ist EINE Fläche, die von
// Abschnitt zu Abschnitt fährt (components/gleit-marker.tsx).

import { useEffect, useRef, useState } from "react";
import { GleitMarker, useGleitMarker } from "@/components/gleit-marker";
import type { PlanSection } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** Der Abschnitt hängt an der `id` seiner Überschrift (`aria-labelledby`). */
const HEADING: Record<PlanSection["key"], string> = {
  content: "plan-content",
  review: "plan-review",
  reports: "plan-reports",
  status: "plan-city-status",
  indicators: "plan-indicators",
  measures: "plan-measures",
  places: "plan-places",
  decisions: "plan-decisions",
};

function sectionOf(key: PlanSection["key"]): HTMLElement | null {
  return document.getElementById(HEADING[key])?.closest("section") ?? null;
}

export function JumpBar({ sections }: { sections: readonly PlanSection[] }) {
  const [active, setActive] = useState<PlanSection["key"] | null>(sections[0]?.key ?? null);
  const { gruppeRef, markerRef } = useGleitMarker(active ?? "");
  const bar = useRef<HTMLElement | null>(null);
  // Nach einem Klick gilt das angeklickte Ziel, bis wieder von Hand gerollt wird: Breit stehen die
  // Beschlüsse NEBEN dem Inhalt — dort entscheidet die Lage nicht, was gemeint war.
  const pinned = useRef(false);

  useEffect(() => {
    let frame = 0;
    const measure = () => {
      frame = 0;
      if (pinned.current) return;
      const line = (bar.current?.getBoundingClientRect().bottom ?? 0) + 24;
      let best: { key: PlanSection["key"]; top: number } | null = null;
      for (const s of sections) {
        const top = sectionOf(s.key)?.getBoundingClientRect().top;
        // Der Abschnitt, dessen Anfang zuletzt unter der Leiste durchgelaufen ist; bei Gleichstand der frühere.
        if (top != null && top <= line && (!best || top > best.top)) best = { key: s.key, top };
      }
      setActive(best?.key ?? sections[0]?.key ?? null);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(measure); };
    const release = () => { pinned.current = false; };
    // `capture`: Am Schreibtisch rollt nicht das Fenster, sondern der Inhaltsbereich.
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("wheel", release, { passive: true });
    window.addEventListener("touchmove", release, { passive: true });
    window.addEventListener("keydown", release);
    measure();
    return () => {
      if (frame) cancelAnimationFrame(frame);
      document.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("wheel", release);
      window.removeEventListener("touchmove", release);
      window.removeEventListener("keydown", release);
    };
  }, [sections]);

  // Der aktive Punkt bleibt in der seitwärts rollenden Leiste im Bild.
  useEffect(() => {
    const group = gruppeRef.current;
    const chip = group?.querySelector<HTMLElement>('[data-aktiv="true"]');
    if (!group || !chip) return;
    const g = group.getBoundingClientRect();
    const c = chip.getBoundingClientRect();
    if (c.left < g.left + 8) group.scrollBy({ left: c.left - g.left - 16 });
    else if (c.right > g.right - 8) group.scrollBy({ left: c.right - g.right + 16 });
  }, [active, gruppeRef]);

  if (sections.length < 2) return null;

  const jump = (key: PlanSection["key"]) => {
    const section = sectionOf(key);
    if (!section) return;
    pinned.current = true;
    setActive(key);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    section.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <nav ref={bar} aria-label="Abschnitte dieser Seite"
      className="print-hidden sticky top-[calc(env(safe-area-inset-top)+3.8125rem)] z-10 -mx-1 mt-2 bg-background/95 px-1 py-1.5 backdrop-blur desk:top-0">
      <div ref={gruppeRef} className="gleit-gruppe scrollbar-none relative flex gap-1 overflow-x-auto">
        <GleitMarker markerRef={markerRef} radius="9999px" />
        {sections.map((s) => {
          const on = s.key === active;
          return (
            <button key={s.key} type="button" onClick={() => jump(s.key)} aria-current={on ? "true" : undefined}
              data-aktiv={on ? "true" : undefined}
              className={cn("gleit-knopf relative inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-[13px] font-medium active:scale-[0.97]",
                on ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}>
              {s.label}
              {s.count != null && <span className="font-mono text-[10.5px] tabular-nums opacity-80">{s.count}</span>}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
