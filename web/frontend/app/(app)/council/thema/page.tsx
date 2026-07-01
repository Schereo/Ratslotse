"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft, Tag } from "lucide-react";
import { EntityDetail } from "@/lib/types";
import { Spinner, EmptyState } from "@/components/ui";
import { DecisionLinkCard, PartyBadge, FieldBadge, formatEuro } from "@/components/decision-ui";
import { ENTITY_KIND } from "@/components/council-entities";
import { useFetch } from "@/lib/use-fetch";

// Leaflet needs `window` → load the map client-only.
const EntityMap = dynamic(() => import("@/components/entity-map").then((m) => m.EntityMap), {
  ssr: false,
  loading: () => <div className="h-64 w-full animate-pulse rounded-lg border border-border bg-muted/40" />,
});

function EntityInner() {
  const slug = useSearchParams().get("slug");
  const router = useRouter();
  const { data, loading } = useFetch<EntityDetail>(slug ? `/council/entity/${slug}` : null);

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data) {
    return <EmptyState icon={Tag} title="Thema nicht gefunden" hint="Zu diesem Begriff gibt es (noch) keine Sammelseite." />;
  }
  const k = ENTITY_KIND[data.entity.kind] ?? ENTITY_KIND.projekt;
  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Zurück
      </button>

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
    <Suspense fallback={<div className="py-10"><Spinner /></div>}>
      <EntityInner />
    </Suspense>
  );
}
