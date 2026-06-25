"use client";

import { useState } from "react";
import Link from "next/link";
import { MapPin, Building2, Boxes, Search, Tag } from "lucide-react";
import { Entity } from "@/lib/types";
import { Card, Input, Spinner, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";

export const ENTITY_KIND: Record<string, { label: string; Icon: typeof MapPin }> = {
  ort: { label: "Ort", Icon: MapPin },
  organisation: { label: "Organisation", Icon: Building2 },
  projekt: { label: "Projekt", Icon: Boxes },
};

export function EntityChip({ e }: { e: Entity }) {
  const k = ENTITY_KIND[e.kind] ?? ENTITY_KIND.projekt;
  return (
    <Link href={`/council/thema/${e.slug}`} className="block">
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

  if (loading) return <div className="py-10"><Spinner /></div>;
  const all = data?.entities ?? [];
  if (all.length === 0) {
    return <EmptyState icon={Tag} title="Noch keine Themen" hint="Es wurden noch keine wiederkehrenden Eigennamen aus den Beschlüssen extrahiert." />;
  }
  const needle = q.trim().toLowerCase();
  const filtered = needle ? all.filter((e) => e.name.toLowerCase().includes(needle)) : all;
  return (
    <div className="mt-4 space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Thema suchen — z. B. Fliegerhorst, Klinikum, Nadorster Straße"
          value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">
        {filtered.length} Themen — wiederkehrende Projekte, Orte und Organisationen, klicken für alle Beschlüsse dazu.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {filtered.map((e) => <EntityChip key={e.slug} e={e} />)}
      </div>
    </div>
  );
}
