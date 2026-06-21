"use client";

import { cn } from "@/lib/utils";

/** Page numbers to render, with "…" gaps for long ranges. */
function pageItems(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const items: (number | "…")[] = [1];
  const left = Math.max(2, current - 1);
  const right = Math.min(total - 1, current + 1);
  if (left > 2) items.push("…");
  for (let i = left; i <= right; i++) items.push(i);
  if (right < total - 1) items.push("…");
  items.push(total);
  return items;
}

export function Pagination({
  page,
  totalPages,
  onChange,
  className,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
  className?: string;
}) {
  if (totalPages <= 1) return null;
  const items = pageItems(page, totalPages);
  const base = "flex h-9 min-w-9 items-center justify-center rounded-md px-2 text-sm font-medium transition-colors";
  const ghost = "text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40";

  return (
    <nav className={cn("flex flex-wrap items-center justify-center gap-1", className)} aria-label="Seitennavigation">
      <button type="button" className={cn(base, ghost)} onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="Vorherige Seite">
        ‹
      </button>
      {items.map((it, i) =>
        it === "…" ? (
          <span key={`gap-${i}`} className="px-1 text-muted-foreground">…</span>
        ) : (
          <button
            key={it}
            type="button"
            onClick={() => onChange(it)}
            aria-current={it === page ? "page" : undefined}
            className={cn(base, it === page ? "bg-primary text-primary-foreground" : ghost)}
          >
            {it}
          </button>
        ),
      )}
      <button type="button" className={cn(base, ghost)} onClick={() => onChange(page + 1)} disabled={page >= totalPages} aria-label="Nächste Seite">
        ›
      </button>
    </nav>
  );
}
