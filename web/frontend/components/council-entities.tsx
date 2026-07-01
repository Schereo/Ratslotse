"use client";

import { useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { MapPin, Building2, Boxes, Search, List, Map as MapIcon } from "lucide-react";
import { Entity, EntityMapPoint } from "@/lib/types";
import { Card, Input, Spinner, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { themaHref } from "@/lib/routes";
import { KIND_COLOR } from "@/components/council-map";

// Leaflet needs `window`, so the map is client-only (ssr:false).
const CouncilMap = dynamic(() => import("@/components/council-map").then((m) => m.CouncilMap), {
  ssr: false,
  loading: () => <div className="flex h-[28rem] items-center justify-center rounded-lg border border-border"><Spinner /></div>,
});

export const ENTITY_KIND: Record<string, { label: string; Icon: typeof MapPin }> = {
  ort: { label: "Ort", Icon: MapPin },
  organisation: { label: "Organisation", Icon: Building2 },
  projekt: { label: "Projekt", Icon: Boxes },
};

export function EntityChip({ e }: { e: Entity }) {
  const k = ENTITY_KIND[e.kind] ?? ENTITY_KIND.projekt;
  return (
    <Link href={themaHref(e.slug)} className="block">
      <Card className="card-interactive flex items-center gap-2.5 p-3">
        <k.Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{e.name}</span>
        <span className="shrink-0 rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground" title="Beschlüsse">{e.n}</span>
      </Card>
    </Link>
  );
}

export function EntitiesTab() {
  const { data, loading } = useFetch<{ entities: Entity[] }>("/council/entities");
  const [q, setQ] = useState("");
  const [view, setView] = useState<"list" | "map">("list");

  if (loading) return <div className="py-10"><Spinner /></div>;
  const all = data?.entities ?? [];
  if (all.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Themen" hint="Es wurden noch keine wiederkehrenden Eigennamen aus den Beschlüssen extrahiert." />;
  }
  const needle = q.trim().toLowerCase();
  const filtered = needle ? all.filter((e) => e.name.toLowerCase().includes(needle)) : all;

  return (
    <div className="mt-4 space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input data-search className="pl-9" placeholder="Thema suchen — z. B. Fliegerhorst, Klinikum, Nadorster Straße"
            value={q} onChange={(e) => setQ(e.target.value)} disabled={view === "map"} />
        </div>
        <div className="flex shrink-0 rounded-lg border border-border p-0.5">
          {([["list", "Liste", List], ["map", "Karte", MapIcon]] as const).map(([v, lbl, Icon]) => (
            <button key={v} type="button" onClick={() => setView(v)}
              className={cn("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm transition-colors",
                view === v ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:text-foreground")}>
              <Icon className="h-4 w-4" /> <span className="hidden sm:inline">{lbl}</span>
            </button>
          ))}
        </div>
      </div>

      {view === "list" ? (
        <>
          <p className="text-xs text-muted-foreground">
            {filtered.length} Themen — wiederkehrende Projekte, Orte und Organisationen, klicken für alle Beschlüsse dazu.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {filtered.map((e) => <EntityChip key={e.slug} e={e} />)}
          </div>
        </>
      ) : (
        <MapView />
      )}
    </div>
  );
}

function MapView() {
  const { data, loading } = useFetch<{ entities: EntityMapPoint[] }>("/council/entities-map");
  if (loading) return <div className="flex h-[28rem] items-center justify-center rounded-lg border border-border"><Spinner /></div>;
  const points = data?.entities ?? [];
  if (points.length === 0) {
    return <EmptyState mascot="search" title="Noch keine verorteten Themen" hint="Sobald Orte und Straßen geokodiert sind, erscheinen sie hier auf der Karte." />;
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {points.length} verortete Themen — Punktgröße zeigt die Zahl der Beschlüsse, klicken öffnet das Thema.
      </p>
      <CouncilMap points={points} />
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {Object.entries(ENTITY_KIND).map(([kind, { label }]) => (
          <span key={kind} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: KIND_COLOR[kind] }} /> {label}
          </span>
        ))}
      </div>
    </div>
  );
}
