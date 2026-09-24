"use client";

import Link from "next/link";
import { ArrowRight, X } from "lucide-react";
import type { DecisionDetail } from "@/lib/types";
import { Card, formatDate, Skeleton } from "@/components/ui";
import { OutcomeBadge } from "@/components/decision-ui";
import { shortCommittee } from "@/lib/committees";
import { decisionHref } from "@/lib/routes";
import { useFetch } from "@/lib/use-fetch";

/** Ein Beschluss als Vorschau neben einer Liste — Tagesordnung, Suchtreffer.
 *
 *  Auf breiten Schirmen (docs/plan-breite-schirme.md) öffnet ein Klick auf eine
 *  Zeile nicht mehr die ganze Seite, sondern diese Spalte daneben: Die Liste
 *  bleibt stehen, man springt von Punkt zu Punkt, ohne jedes Mal zurück zu
 *  müssen. Die Vorschau zeigt, was man zum Einordnen braucht — Ergebnis,
 *  Kurzfassung, Wortlaut — und führt für alles andere auf die volle Seite.
 */
export function BeschlussVorschau({ id, onSchliessen, className }: {
  id: number;
  onSchliessen?: () => void;
  className?: string;
}) {
  const { data, loading } = useFetch<DecisionDetail>(`/council/decision/${id}`, { quiet: true });
  const d = data?.decision;

  return (
    <Card className={className} aria-live="polite" aria-busy={loading}>
      <div className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3">
        <p className="font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground">Vorschau</p>
        {onSchliessen && (
          <button type="button" onClick={onSchliessen} aria-label="Vorschau schließen"
            className="-m-1 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      {loading || !d ? (
        loading ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <p className="p-4 text-sm text-muted-foreground">Dieser Beschluss lässt sich gerade nicht laden.</p>
        )
      ) : (
        <div className="p-4">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted-foreground">
            <OutcomeBadge outcome={d.outcome} />
            <span>{shortCommittee(d.committee)} · {formatDate(d.session_date)}{d.item_number ? ` · TOP ${d.item_number}` : ""}</span>
          </div>
          <h2 className="mt-2 font-display text-lg font-bold leading-snug text-foreground [overflow-wrap:anywhere]">
            {d.title}
          </h2>
          {d.simple_summary && (
            <div className="mt-3 rounded-xl border border-signal/30 bg-signal/[0.05] p-3">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-orange-800 dark:text-orange-300">
                Lotti erklärt&rsquo;s einfach
              </p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">{d.simple_summary}</p>
            </div>
          )}
          {d.official_text && (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Amtlicher Wortlaut</p>
              {/* Gekappt: Ein Wortlaut läuft bis über eine Bildschirmseite, und
                  die Vorschau klebt neben der Liste — der Rest steht auf der
                  vollen Seite, der Knopf darunter führt hin. */}
              <p className="mt-1 line-clamp-[14] text-sm leading-relaxed text-foreground">{d.official_text}</p>
            </div>
          )}
          <Link href={decisionHref(d.id)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
            Ganze Seite öffnen <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}
    </Card>
  );
}

/** Ein Klick, den die Vorschau abfangen darf: linke Taste, keine Modifikator-
 *  Taste. Cmd-/Strg-Klick und die mittlere Taste öffnen weiter einen neuen
 *  Tab — wer das gewohnt ist, soll es auch hier bekommen. */
export function istVorschauKlick(e: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }): boolean {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}
