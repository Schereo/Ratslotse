"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { MapPin, Building2, Boxes, Search, ChevronDown, X } from "lucide-react";
import { Entity, EntityMapPoint } from "@/lib/types";
import { Card, Input, Spinner, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { themaHref } from "@/lib/routes";
import { KIND_COLOR } from "@/components/council-map";
import { loadStadtteile, stadtteilFor, stadtteileImWahlbereich, type StadtteilFeature } from "@/lib/stadtteile";

// Leaflet needs `window`, so the map is client-only (ssr:false).
const CouncilMap = dynamic(() => import("@/components/council-map").then((m) => m.CouncilMap), {
  ssr: false,
  loading: () => <div className="flex h-[22rem] items-center justify-center rounded-xl border border-border"><Spinner /></div>,
});

export const ENTITY_KIND: Record<string, { label: string; plural: string; Icon: typeof MapPin }> = {
  ort: { label: "Ort", plural: "Orte", Icon: MapPin },
  organisation: { label: "Organisation", plural: "Organisationen", Icon: Building2 },
  projekt: { label: "Projekt", plural: "Projekte", Icon: Boxes },
};

export function EntityChip({ e }: { e: Entity }) {
  const k = ENTITY_KIND[e.kind] ?? ENTITY_KIND.projekt;
  return (
    <Link href={themaHref(e.slug)} className="block">
      <Card className="card-interactive flex items-center gap-2.5 p-3">
        <k.Icon className="h-4 w-4 shrink-0" style={{ color: KIND_COLOR[e.kind] ?? KIND_COLOR.projekt }} />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{e.name}</span>
        <span className="shrink-0 rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground" title="Beschlüsse">{e.n}</span>
      </Card>
    </Link>
  );
}

/** „zuletzt Mai 2026" aus einem ISO-Datum. */
function lastLabel(d?: string | null): string | null {
  if (!d) return null;
  const date = new Date(d);
  if (isNaN(date.getTime())) return null;
  return date.toLocaleDateString("de-DE", { month: "short", year: "numeric" });
}

/** Größere Karte für die gerade aktiven Top-Themen: die 12-Monats-Zahl trägt,
 *  Gesamtzahl und letzte Sitzung liefern den Langzeit-Kontext. */
function TopEntityCard({ e, maxRecent }: { e: Entity; maxRecent: number }) {
  const k = ENTITY_KIND[e.kind] ?? ENTITY_KIND.projekt;
  const color = KIND_COLOR[e.kind] ?? KIND_COLOR.projekt;
  const recent = e.n_recent ?? 0;
  const last = lastLabel(e.last_date);
  return (
    <Link href={themaHref(e.slug)} className="block">
      <Card className="card-interactive h-full p-4">
        <div className="flex items-start justify-between gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ background: `${color}1a`, color }}>
            <k.Icon className="h-5 w-5" />
          </span>
          <span className="text-right">
            <span className="block text-xl font-bold tabular-nums leading-none text-foreground">{recent}</span>
            <span className="text-[11px] text-muted-foreground">in 12 Monaten</span>
          </span>
        </div>
        <p className="mt-2.5 truncate font-medium text-foreground" title={e.name}>{e.name}</p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full" style={{ width: `${Math.max(6, (recent / maxRecent) * 100)}%`, background: color }} />
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          {e.n} insgesamt{last ? ` · zuletzt ${last}` : ""}
        </p>
      </Card>
    </Link>
  );
}

type KindFilter = "" | "ort" | "organisation" | "projekt";

/** Kompakter Mehrfach-Auswahl-Popover für die 31 Stadtteile — filtert die
 *  Punkte auf der Karte (die Liste darunter bleibt vollständig). */
function StadtteilFilter({ names, counts, selected, onChange }: {
  names: string[];
  counts: Record<string, number>;
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name); else next.add(name);
    onChange(next);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
          selected.size > 0 ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground",
        )}
      >
        <MapPin className="h-3.5 w-3.5" />
        {selected.size > 0 ? `Stadtteile · ${selected.size}` : "Stadtteile"}
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute right-0 z-[60] mt-2 w-72 rounded-xl border border-border bg-card p-3 shadow-lg">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-foreground">Karte nach Stadtteilen filtern</p>
            {selected.size > 0 && (
              <button type="button" onClick={() => onChange(new Set())}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline">
                <X className="h-3 w-3" /> Zurücksetzen
              </button>
            )}
          </div>
          {/* Schnellauswahl: die 6 Kommunalwahl-Wahlbereiche togglen ihre
              Stadtteile als Gruppe (aktiv = alle Stadtteile des Bereichs an). */}
          <div className="mt-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">Wahlbereiche</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {[1, 2, 3, 4, 5, 6].map((wb) => {
                const gruppe = stadtteileImWahlbereich(wb);
                const active = gruppe.every((n) => selected.has(n));
                return (
                  <button
                    key={wb}
                    type="button"
                    title={gruppe.join(", ")}
                    onClick={() => {
                      const next = new Set(selected);
                      if (active) gruppe.forEach((n) => next.delete(n));
                      else gruppe.forEach((n) => next.add(n));
                      onChange(next);
                    }}
                    className={cn(
                      "rounded-md border px-2 py-1 text-[11px] font-medium tabular-nums transition-colors",
                      active ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground",
                    )}
                  >
                    WB {wb}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="mt-2 grid max-h-64 grid-cols-2 gap-x-3 gap-y-0.5 overflow-y-auto overscroll-contain pr-1">
            {names.map((name) => (
              <label key={name} className="flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-xs text-foreground hover:bg-muted">
                <input
                  type="checkbox"
                  checked={selected.has(name)}
                  onChange={() => toggle(name)}
                  className="h-3.5 w-3.5 rounded border-border accent-[hsl(var(--primary))]"
                />
                <span className="min-w-0 flex-1 truncate">{name}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground/70">{counts[name] ?? 0}</span>
              </label>
            ))}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            Grenzen: © OpenStreetMap-Mitwirkende · Wahlbereiche: Stadt Oldenburg (openGEOdata)
          </p>
        </div>
      )}
    </div>
  );
}

export function EntitiesTab() {
  const { data, loading } = useFetch<{ entities: Entity[] }>("/council/entities");
  const { data: geo, loading: geoLoading } = useFetch<{ entities: EntityMapPoint[] }>("/council/entities-map");
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<KindFilter>("");
  const [stadtteile, setStadtteile] = useState<StadtteilFeature[]>([]);
  const [selectedST, setSelectedST] = useState<Set<string>>(new Set());
  useEffect(() => {
    void loadStadtteile().then(setStadtteile);
  }, []);

  const all = useMemo(() => data?.entities ?? [], [data]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { ort: 0, organisation: 0, projekt: 0 };
    for (const e of all) c[e.kind] = (c[e.kind] ?? 0) + 1;
    return c;
  }, [all]);

  // Stadtteil je Kartenpunkt (einmal berechnet); Punkte außerhalb Oldenburgs → null.
  const pointST = useMemo(() => {
    const m = new Map<string, string | null>();
    if (stadtteile.length) {
      for (const p of geo?.entities ?? []) m.set(p.slug, stadtteilFor(p.lat, p.lon, stadtteile));
    }
    return m;
  }, [geo, stadtteile]);
  const stCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const st of pointST.values()) if (st) c[st] = (c[st] ?? 0) + 1;
    return c;
  }, [pointST]);

  // Punkte + Grenz-Overlays memoisiert — die Karte remountet sonst bei jedem
  // Tastendruck in der Suche (Array-Identität ist ihre Effect-Dependency).
  const points = useMemo(
    () => (geo?.entities ?? [])
      .filter((p) => (kind ? p.kind === kind : true))
      .filter((p) => (selectedST.size ? selectedST.has(pointST.get(p.slug) ?? "") : true)),
    [geo, kind, selectedST, pointST],
  );
  const outlines = useMemo(
    () => (selectedST.size ? stadtteile.filter((f) => selectedST.has(f.properties.name)) : undefined),
    [stadtteile, selectedST],
  );

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (all.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Themen" hint="Es wurden noch keine wiederkehrenden Eigennamen aus den Beschlüssen extrahiert." />;
  }

  const needle = q.trim().toLowerCase();
  const filtered = all
    .filter((e) => (kind ? e.kind === kind : true))
    .filter((e) => (needle ? e.name.toLowerCase().includes(needle) : true));
  const maxRecent = Math.max(1, ...all.map((e) => e.n_recent ?? 0));

  // Ohne Suche: die gerade AKTIVEN Themen groß (12-Monats-Beschlüsse, dann
  // letzte Sitzung) — nicht die Lebenszeit-Summe seit 2018, sonst thront ein
  // seit Jahren ruhendes Thema ewig oben. Der Rest kompakt nach Gesamtzahl.
  // Mit Suche: einfach die Treffer.
  const byActivity = [...filtered].sort(
    (a, b) =>
      (b.n_recent ?? 0) - (a.n_recent ?? 0) ||
      (b.last_date ?? "").localeCompare(a.last_date ?? "") ||
      b.n - a.n,
  );
  const top = needle ? [] : byActivity.filter((e) => (e.n_recent ?? 0) > 0).slice(0, 6);
  const topSlugs = new Set(top.map((e) => e.slug));
  const rest = needle ? filtered : filtered.filter((e) => !topSlugs.has(e.slug));

  return (
    <div className="mt-4 space-y-4">
      {/* Die Karte zuerst — sie ist der Blickfang der Seite, kein verstecktes
          Toggle-Feature. Kind-Chips unten filtern Karte UND Liste. Während der
          Geo-Fetch läuft, hält ein Platzhalter dieselbe Höhe (kein Pop-in-Shift). */}
      {geoLoading ? (
        <div className="flex h-[38vh] min-h-[17rem] max-h-[26rem] items-center justify-center rounded-xl border border-border">
          <Spinner />
        </div>
      ) : (geo?.entities.length ?? 0) > 0 ? (
        <div className="relative">
          <CouncilMap points={points} outlines={outlines} className="h-[38vh] min-h-[17rem] max-h-[26rem] rounded-xl" />
          <p className="pointer-events-none absolute bottom-2.5 left-2.5 z-[500] rounded-md bg-background/85 px-2 py-1 text-[11px] text-muted-foreground backdrop-blur">
            {selectedST.size > 0
              ? `${points.length} von ${geo!.entities.length} Punkten · ${selectedST.size} ${selectedST.size === 1 ? "Stadtteil" : "Stadtteile"} ausgewählt`
              : `${points.length} verortete Themen · Punktgröße = Beschlüsse · klicken öffnet das Thema`}
          </p>
        </div>
      ) : null}

      {/* Suche + Kind-Filter (Farbpunkte = Kartenlegende) */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[14rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input data-search className="pl-9" placeholder="Thema suchen — z. B. Fliegerhorst, Klinikum, Nadorster Straße"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <button type="button" onClick={() => setKind("")}
            className={cn("rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              kind === "" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
            Alle · {all.length}
          </button>
          {(Object.keys(ENTITY_KIND) as KindFilter[]).map((k) => k && (
            <button key={k} type="button" onClick={() => setKind(kind === k ? "" : k)}
              className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                kind === k ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
              <span className="h-2 w-2 rounded-full" style={{ background: KIND_COLOR[k] }} />
              {ENTITY_KIND[k].plural} · {counts[k] ?? 0}
            </button>
          ))}
          {stadtteile.length > 0 && (geo?.entities.length ?? 0) > 0 && (
            <StadtteilFilter
              names={stadtteile.map((f) => f.properties.name)}
              counts={stCounts}
              selected={selectedST}
              onChange={setSelectedST}
            />
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState mascot="confused" title="Nichts gefunden" hint="Anderen Suchbegriff probieren oder Filter zurücksetzen." />
      ) : (
        <>
          {top.length > 0 && (
            <>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">Gerade aktiv</p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {top.map((e) => <TopEntityCard key={e.slug} e={e} maxRecent={maxRecent} />)}
              </div>
            </>
          )}
          {rest.length > 0 && (
            <>
              {top.length > 0 && (
                <p className="pt-1 text-xs text-muted-foreground">
                  Alle weiteren Themen (nach Gesamtzahl) — klicken für sämtliche Beschlüsse dazu.
                </p>
              )}
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {rest.map((e) => <EntityChip key={e.slug} e={e} />)}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
