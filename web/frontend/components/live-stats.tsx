"use client";

import { useEffect, useRef, useState } from "react";
import { useCountUp } from "@/lib/use-countup";

type Stats = { decisions: number; sessions: number; entities: number };

// Real headline numbers (public endpoint, no auth) that count up when scrolled into view.
// `inline` (RL-302): einzeilige Belegzeile unter den Hero-CTAs statt 3er-Grid.
export function LiveStats({ inline = false }: { inline?: boolean } = {}) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/council/public-stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setStats(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setInView(true); io.disconnect(); } },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const run = inView && !!stats;
  const decisions = useCountUp(stats?.decisions ?? 0, run);
  const sessions = useCountUp(stats?.sessions ?? 0, run);
  const entities = useCountUp(stats?.entities ?? 0, run);

  const items = [
    { n: decisions, label: "Beschlüsse" },
    { n: sessions, label: "Sitzungen" },
    { n: entities, label: "Themen" },
  ];

  if (inline) {
    return (
      <p ref={ref} className="mt-6 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-sm text-muted-foreground lg:justify-start">
        {items.map((it, i) => (
          <span key={it.label} className="inline-flex items-baseline gap-1.5">
            {i > 0 && <span aria-hidden className="pr-2 text-muted-foreground/50">·</span>}
            <span className="font-display text-base font-bold tabular-nums text-foreground">
              {stats ? it.n.toLocaleString("de-DE") : "—"}
            </span>
            {it.label}
          </span>
        ))}
      </p>
    );
  }

  return (
    <div ref={ref} className="mx-auto mt-14 grid max-w-lg grid-cols-3 gap-4 sm:gap-8">
      {items.map((it) => (
        <div key={it.label} className="text-center">
          <div className="text-3xl font-bold tabular-nums text-foreground sm:text-4xl">
            {stats ? it.n.toLocaleString("de-DE") : "—"}
          </div>
          <div className="mt-1 text-sm text-muted-foreground">{it.label}</div>
        </div>
      ))}
    </div>
  );
}
