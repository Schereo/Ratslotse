import { cn } from "@/lib/utils";

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} style={style} />;
}

/** Content-shaped placeholder für Detailseiten (Beschluss/Person/Thema). */
export function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-3xl" aria-busy="true" aria-live="polite">
      <Skeleton className="h-4 w-16" />
      <Skeleton className="mt-4 h-3 w-48" />
      <Skeleton className="mt-2 h-6 w-4/5" />
      <div className="mt-3 flex gap-1.5">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <div className="mt-5 rounded-xl border border-border bg-card p-4">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="mt-2 h-3 w-full" />
        <Skeleton className="mt-2 h-3 w-2/3" />
      </div>
      <Skeleton className="mt-8 h-3 w-24" />
      <div className="mt-3 space-y-2">
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    </div>
  );
}

/** Diagramm-Platzhalter (Design 29a, P2) — Kopfzeile, Balkenfeld, Achse.
 *
 *  Suche, Detail und Themen zeigten formgleiche Skelette, Analyse und Quiz
 *  dagegen einen zentrierten Spinner auf leerer Fläche: Man wusste weder, was
 *  gleich kommt, noch wie viel, und der Inhalt sprang danach ins Bild. Mit der
 *  Form steht das Layout sofort — die Seite wirkt so schnell, wie sie ist.
 */
export function ChartSkeleton({ bars = 7, className }: { bars?: number; className?: string }) {
  // Feste, unregelmäßige Höhen statt Zufall: Ein Skelett darf bei jedem Render
  // nicht anders aussehen (und Math.random bräche die Hydration).
  const hoehen = [58, 82, 44, 96, 67, 38, 74, 90, 52, 79, 63, 86];
  return (
    <div className={cn("rounded-xl border border-border bg-card p-4", className)} aria-busy="true" aria-live="polite">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="mt-2 h-6 w-20" />
      <div className="mt-4 flex h-32 items-end gap-2">
        {Array.from({ length: bars }).map((_, i) => (
          <Skeleton key={i} className="flex-1 rounded-t-md" style={{ height: `${hoehen[i % hoehen.length]}%` }} />
        ))}
      </div>
      <div className="mt-3 flex justify-between">
        <Skeleton className="h-2.5 w-10" />
        <Skeleton className="h-2.5 w-10" />
        <Skeleton className="h-2.5 w-10" />
      </div>
    </div>
  );
}

/** Tabellen-Platzhalter (Design 29a, P2) — für Listen mit Zeilenraster
 *  (Mitglieder, Ziele, Admin-Tabellen). */
export function TableSkeleton({ rows = 6, cols = 3 }: { rows?: number; cols?: number }) {
  const breiten = ["w-2/5", "w-1/4", "w-1/6", "w-1/5"];
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card" aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-4 border-b border-border bg-muted/30 px-4 py-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className={cn("h-3", breiten[i % breiten.length])} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 border-b border-border/60 px-4 py-3 last:border-b-0">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={cn("h-3.5", breiten[(r + c) % breiten.length])} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Content-shaped placeholder for lists of result/topic cards. */
export function CardListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="mt-2.5 h-4 w-3/4" />
          <Skeleton className="mt-2 h-3 w-full" />
          <Skeleton className="mt-1.5 h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}
