"use client";

import { cn } from "@/lib/utils";
import { useGleitMarker, GleitMarker } from "@/components/gleit-marker";

/** Wie viele Felder die Leiste hat — IMMER dieselbe Zahl, sobald es überhaupt
 *  mehr Seiten als Felder gibt. */
const FELDER = 7;

/** Die Seitenzahlen, mit „…" für die Lücken.
 *
 *  Die Leiste hält ihre Feldzahl fest. Vorher wuchs sie mit der Position — auf
 *  Seite 1 standen vier Felder da (`1 2 … 18`), auf Seite 2 fünf, auf Seite 4
 *  sieben. Jeder Klick schob damit alle Zahlen nach rechts und ließ ein neues
 *  Feld erscheinen: Man klickte auf die 2 und die halbe Leiste wanderte unter
 *  dem Finger weg (Tim, 03.09.2026: „sieht immer noch ein wenig weird aus …
 *  sollte so clock mäßig weiterklicken").
 *
 *  Jetzt verschiebt sich das FENSTER statt zu wachsen: Am Anfang und am Ende
 *  liegen die Zahlen fest und nur die Markierung rückt weiter — dort fühlt es
 *  sich an wie ein Zählwerk. In der Mitte steht die Markierung still und die
 *  Zahlen wandern; anders geht es nicht, wenn 18 Seiten in 7 Felder sollen. */
function pageItems(current: number, total: number): (number | "…")[] {
  if (total <= FELDER) return Array.from({ length: total }, (_, i) => i + 1);
  // Vier Zahlen am Anfang: 1 2 3 4 5 … 18
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  // Vier am Ende: 1 … 14 15 16 17 18
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  // Sonst das Fenster um die aktuelle Seite: 1 … 8 9 10 … 18
  return [1, "…", current - 1, current, current + 1, "…", total];
}

export function Pagination({
  page,
  totalPages,
  onChange,
  className,
  compact = false,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
  className?: string;
  /** Kleine Ausführung für die Zeile neben dem Treffer-Zähler (Tims Wunsch
   *  12.08.): dieselben Bausteine, nur leiser — die große, mittige Leiste
   *  über der Liste wirkte wie ein eigener Inhaltsblock. */
  compact?: boolean;
}) {
  // Der Schlüssel ist die Seite: Bei jedem Wechsel misst die Markierung neu
  // und fährt zum neuen Feld.
  const { gruppeRef, markerRef } = useGleitMarker(String(page));
  if (totalPages <= 1) return null;
  const items = pageItems(page, totalPages);
  // Druck-Feedback wie an jedem anderen Ziel der App: Blättern ist ein Klick
  // auf ein kleines Feld, und die Antwort darauf kommt erst mit der neuen
  // Liste — bis dahin bestätigt wenigstens der Knopf, dass er getroffen wurde.
  // Der kurze Takt für alle drei Eigenschaften: Ein Seitenknopf ist kein Weg,
  // sondern ein Schalter (s. DESIGNSPRACHE.md § 7).
  const zug = "transition-[color,background-color,transform] duration-tipp ease-out-strong active:scale-90";
  const base = compact
    ? `flex h-7 min-w-7 items-center justify-center rounded-md px-1.5 text-xs font-medium ${zug}`
    : `flex h-9 min-w-9 items-center justify-center rounded-md px-2 text-sm font-medium ${zug}`;
  const ghost = "text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40";

  return (
    <nav
      ref={gruppeRef}
      className={cn("gleit-gruppe relative flex flex-wrap items-center gap-1", compact ? "justify-end gap-0.5" : "justify-center", className)}
      aria-label="Seitennavigation"
    >
      {/* Rastet ein, statt nur anzukommen (`--ease-back-out` schwingt kurz
          über). Bei einem Feld von 36 px sind das gut drei Pixel — genug, dass
          der Klick sich mechanisch anfühlt, zu wenig, um zu wackeln. */}
      <GleitMarker
        markerRef={markerRef}
        radius="calc(var(--radius) - 2px)"
        farbe="hsl(var(--primary))"
        kurve="var(--ease-back-out)"
      />
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
            data-aktiv={it === page ? "true" : undefined}
            className={cn(base, "gleit-knopf relative", it === page ? "bg-primary text-primary-foreground" : ghost)}
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
