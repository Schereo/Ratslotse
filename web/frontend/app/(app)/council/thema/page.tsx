"use client";

import {Suspense, useEffect } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { EntityDetail, RelatedEntity } from "@/lib/types";
import { DetailSkeleton, EmptyState } from "@/components/ui";
import { reportBadgeEvent } from "@/components/badges";
import { DecisionLinkCard, PartyBadge, FieldBadge, formatEuro } from "@/components/decision-ui";
import { ENTITY_KIND } from "@/components/council-entities";
import { useFetch } from "@/lib/use-fetch";
import { themaHref } from "@/lib/routes";
import { ShareButton } from "@/components/share-button";

// Leaflet needs `window` → load the map client-only.
const EntityMap = dynamic(() => import("@/components/entity-map").then((m) => m.EntityMap), {
  ssr: false,
  loading: () => <div className="h-64 w-full animate-pulse rounded-lg border border-border bg-muted/40" />,
});

/** Verwandte Themen als zwei Chip-Zeilen.
 *
 *  Die Trennung ist keine Kosmetik: Belegte Nachbarn (gemeinsame Beschlüsse)
 *  liegen messbar näher am Thema als die semantischen Auffüller — beides gleich
 *  aussehen zu lassen, würde die schwächeren Treffer als gleichwertig ausgeben.
 *  Deshalb eigene Überschrift, und die Belegzahl steht dabei. */
function RelatedThemes({ related }: { related: RelatedEntity[] }) {
  const proven = related.filter((r) => r.rel_type === "belegt");
  const similar = related.filter((r) => r.rel_type !== "belegt");
  if (proven.length === 0 && similar.length === 0) return null;

  const row = (items: RelatedEntity[], heading: string, hint: string, showEvidence: boolean) =>
    items.length === 0 ? null : (
      <div className="mt-4">
        <h2 className="text-sm font-semibold text-muted-foreground">
          {heading} <span className="font-normal">· {hint}</span>
        </h2>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {items.map((r) => {
            const k = ENTITY_KIND[r.kind] ?? ENTITY_KIND.projekt;
            return (
              <Link
                key={r.slug}
                href={themaHref(r.slug)}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground transition-colors hover:border-primary/40 hover:bg-muted"
              >
                <k.Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                {r.name}
                {showEvidence && (
                  <span
                    className="text-xs tabular-nums text-muted-foreground"
                    title={`${r.evidence} gemeinsame ${r.evidence === 1 ? "Beschluss" : "Beschlüsse"}`}
                  >
                    {r.evidence}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>
    );

  return (
    <div className="mt-6">
      {row(proven, "Hängt zusammen mit", "gemeinsam behandelt", true)}
      {row(similar, "Thematisch ähnlich", "inhaltlich verwandt", false)}
    </div>
  );
}

function EntityInner() {
  const slug = useSearchParams().get("slug");
  const router = useRouter();
  // RL-U12: Kartograf — 3 verschiedene Orte geöffnet (Server zählt distinct).
  useEffect(() => {
    if (slug) reportBadgeEvent("map_place", slug);
  }, [slug]);
  const { data, loading } = useFetch<EntityDetail>(slug ? `/council/entity/${slug}` : null);

  if (loading) return <DetailSkeleton />;
  if (!data) {
    return <EmptyState mascot="confused" title="Thema nicht gefunden" hint="Zu diesem Begriff gibt es (noch) keine Sammelseite." />;
  }
  const k = ENTITY_KIND[data.entity.kind] ?? ENTITY_KIND.projekt;
  return (
    <div className="mx-auto max-w-3xl">
      <div className="print-hidden flex items-center justify-between gap-3">
        <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
        <ShareButton path={themaHref(data.entity.slug)} title={`${data.entity.name} — Ratslotse`} />
      </div>

      <div className="mt-3 flex items-center gap-2.5">
        <k.Icon className="h-6 w-6 shrink-0 text-muted-foreground" />
        <h1 className="text-xl font-semibold text-foreground">{data.entity.name}</h1>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {k.label} · {data.decisions.length} {data.decisions.length === 1 ? "Beschluss" : "Beschlüsse"}
        {data.money > 0 && <> · <span className="font-medium text-emerald-700 dark:text-emerald-400">{formatEuro(data.money)}</span> erkannt</>}
      </p>

      {data.description && (
        <p className="mt-4 rounded-lg border border-border bg-muted/40 p-3.5 text-sm leading-relaxed text-foreground/90">
          {data.description}
        </p>
      )}

      {data.geo && (
        <div className="mt-4">
          <EntityMap geo={data.geo} name={data.entity.name} />
        </div>
      )}

      {data.fields.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          {data.fields.map((f) => (
            <span key={f.field} className="inline-flex items-center gap-1">
              <FieldBadge field={f.field} />
              <span className="text-xs text-muted-foreground">{f.n}</span>
            </span>
          ))}
        </div>
      )}

      {data.parties.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Beteiligte Fraktionen:</span>
          {data.parties.map((p) => <PartyBadge key={p} party={p} />)}
        </div>
      )}

      <RelatedThemes related={data.related ?? []} />

      <h2 className="mt-7 text-sm font-semibold text-muted-foreground">Beschlüsse zu diesem Thema</h2>
      <div className="mt-3 space-y-2">
        {data.decisions.map((d) => (
          <DecisionLinkCard key={d.id} id={d.id} title={d.title} committee={d.committee}
            session_date={d.session_date} field={d.policy_field} amount={d.amount_eur} sub={d.summary} />
        ))}
      </div>
    </div>
  );
}

export default function EntityPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <EntityInner />
    </Suspense>
  );
}
