"use client";

import { Suspense } from "react";
import { notFound, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, MapPin, Search, Sparkles } from "lucide-react";
import { DecisionLinkCard } from "@/components/decision-ui";
import { ShareButton } from "@/components/share-button";
import { Button, DetailSkeleton } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { fragenHref, ortHref } from "@/lib/routes";
import type { CouncilDecision } from "@/lib/types";
import type { OrtsbereichEntry } from "@/lib/districts";
import { useZurueck } from "@/lib/zurueck";

interface PlaceDetail {
  place: OrtsbereichEntry;
  children: OrtsbereichEntry[];
  decision_count: number;
  decisions: CouncilDecision[];
}

function PlaceInner() {
  const id = useSearchParams().get("id");
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  const { data, loading } = useFetch<PlaceDetail>(id ? `/council/place/${encodeURIComponent(id)}` : null);

  if (loading) return <DetailSkeleton />;
  if (!data) notFound();
  const place = data.place;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="print-hidden flex items-center justify-between gap-3">
        {zeigeZurueck ? (
          <button onClick={() => zurueck("/council?tab=decisions")}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Zurück
          </button>
        ) : <span />}
        <ShareButton path={ortHref(place.id)} title={`${place.name} — Ratslotse`} />
      </div>

      <div className="mt-4 flex items-start gap-3">
        <span className="rounded-xl bg-primary/10 p-2.5 text-primary"><MapPin className="h-6 w-6" /></span>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{place.kind_label}</p>
          <h1 className="mt-0.5 text-2xl font-semibold text-foreground">{place.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.decision_count} {data.decision_count === 1 ? "Beschluss" : "Beschlüsse"} mit belegtem Ortsbezug
          </p>
        </div>
      </div>

      {place.description && (
        <p className="mt-5 rounded-lg border border-border bg-muted/40 p-4 text-sm leading-relaxed text-foreground/90">
          {place.description}
        </p>
      )}

      {place.parents.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Gehört zu:</span>
          {place.parents.map((parent) => (
            <Link key={parent.id} href={ortHref(parent.id)}
              className="rounded-full border border-border px-3 py-1 text-foreground hover:border-primary/40 hover:bg-muted">
              {parent.name}
            </Link>
          ))}
        </div>
      )}

      {data.children.length > 0 && (
        <div className="mt-5">
          <h2 className="text-sm font-semibold text-muted-foreground">Orte in diesem Bereich</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.children.map((child) => (
              <Link key={child.id} href={ortHref(child.id)}
                className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground hover:border-primary/40 hover:bg-muted">
                {child.name} <span className="text-muted-foreground">· {child.kind_label}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="print-hidden mt-5 flex flex-wrap gap-2">
        <Button asChild>
          <Link href={fragenHref({ q: `Was wurde zu ${place.name} beschlossen?` })}>
            <Sparkles className="mr-2 h-4 w-4" /> KI dazu fragen
          </Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href={`/council?tab=decisions&district=${encodeURIComponent(place.id)}`}>
            <Search className="mr-2 h-4 w-4" /> In Beschlüssen suchen
          </Link>
        </Button>
      </div>

      {place.sources.length > 0 && (
        <div className="mt-6 border-t border-border pt-4">
          <h2 className="text-sm font-semibold text-muted-foreground">Stammdaten-Quellen</h2>
          <div className="mt-2 flex flex-col gap-1.5">
            {place.sources.map((source) => (
              <a key={source.id} href={source.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
                {source.title} <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ))}
          </div>
        </div>
      )}

      <h2 className="mt-8 text-sm font-semibold text-muted-foreground">Beschlüsse mit Ortsbezug</h2>
      {data.decisions.length > 0 ? (
        <div className="mt-3 space-y-2">
          {data.decisions.map((decision) => {
            const evidence = decision.location_matches?.[0]?.evidence;
            return <DecisionLinkCard key={decision.id} id={decision.id} title={decision.title}
              committee={decision.committee} session_date={decision.session_date}
              field={decision.policy_field} amount={decision.amount_eur}
              sub={evidence ? `Ortsbeleg: ${evidence}` : decision.summary} />;
          })}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Noch kein Beschluss ist diesem Ort sicher zugeordnet.</p>
      )}
    </div>
  );
}

export default function PlacePage() {
  return <Suspense fallback={<DetailSkeleton />}><PlaceInner /></Suspense>;
}
