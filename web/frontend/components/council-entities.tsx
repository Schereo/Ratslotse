"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { MapPin, Building2, Boxes, Search, ChevronDown, X } from "lucide-react";
import { Entity, EntityMapPoint } from "@/lib/types";
import { Card, Input, Spinner, TableSkeleton, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { themaHref } from "@/lib/routes";
import { KIND_COLOR } from "@/components/council-map";
import {
  loadOrtsbereiche,
  loadOrtsbereichCatalog,
  ortsbereichFor,
  ortsbereicheImWahlbereich,
  type OrtsbereichEntry,
  type OrtsbereichFeature,
} from "@/lib/districts";

// Form und Höhe der Stadtkarte stehen hier an EINER Stelle — Karte und beide
// Platzhalter (Chunk, Geo-Fetch) müssen sie teilen, sonst springt das Layout
// beim Nachladen.
//
// Seitenverhältnis statt reinem vh-Anteil: 38 vh ergeben auf dem Telefon einen
// fast quadratischen Rahmen (356 × 319), auf dem iPad quer aber einen
// Briefschlitz (1114 × 310, 3,6 : 1). In einen so flachen Rahmen passt die
// Punktwolke nur, wenn Leaflet zwei Zoomstufen herauszoomt — sichtbar waren
// 102 km von Aurich bis Bremen, Oldenburg ein Klecks in der Mitte (Tims
// iPad-Befund). Deshalb: mindestens 38 vh (das Telefon bleibt, wie es ist),
// Form 12 : 5, und nie mehr als die halbe Bildschirmhöhe — unter der Karte
// muss die Filterzeile angeschnitten stehen bleiben, sonst merkt niemand,
// dass es weitergeht. Der frühere Boden `min-h-[17rem]` fällt weg: auf einem
// quer gehaltenen Telefon fraß er 70 % der Höhe.
//
// `w-full` ist Pflicht, nicht Deko: Ohne feste Breite rechnet der Browser sie
// aus Seitenverhältnis und Höhe zurück, sobald `min-h` die Höhe bestimmt — die
// Karte wuchs auf dem Telefon auf 768 px und lief aus dem Bild (gemessen).
const KARTE_RAHMEN = "w-full aspect-[12/5] min-h-[38vh] max-h-[min(30rem,50vh)]";

// Leaflet needs `window`, so the map is client-only (ssr:false).
const CouncilMap = dynamic(() => import("@/components/council-map").then((m) => m.CouncilMap), {
  ssr: false,
  loading: () => <div className={cn(KARTE_RAHMEN, "flex items-center justify-center rounded-xl border border-border")}><Spinner /></div>,
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

/** Kompakter Mehrfach-Auswahl-Popover für die 31 Ortsbereiche — filtert die
 *  Punkte auf der Karte (die Liste darunter bleibt vollständig). */
function OrtsbereichFilter({ names, places, counts, selected, onChange }: {
  names: string[];
  places: OrtsbereichEntry[];
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
        {selected.size > 0 ? `Ortsbereiche · ${selected.size}` : "Ortsbereiche"}
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        // Desktop: Dropdown rechts unter dem Chip. Mobil: unten verankertes
        // Sheet über der Tab-Bar (w-72 + right-0 ragte sonst aus dem Bild, weil
        // der Chip mittig in Zeile 2 sitzt).
        <div className="z-[60] rounded-xl border border-border bg-card p-3 shadow-lg
          max-sm:fixed max-sm:inset-x-3 max-sm:bottom-[calc(5rem+env(safe-area-inset-bottom))] max-sm:max-h-[70vh] max-sm:overflow-y-auto
          sm:absolute sm:right-0 sm:mt-2 sm:w-72">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-foreground">Karte nach Ortsbereichen filtern</p>
            {selected.size > 0 && (
              <button type="button" onClick={() => onChange(new Set())}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline">
                <X className="h-3 w-3" /> Zurücksetzen
              </button>
            )}
          </div>
          {/* Schnellauswahl: die 6 Kommunalwahl-Wahlbereiche togglen ihre
              Ortsbereiche als Gruppe. */}
          {places.length > 0 && <div className="mt-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">Wahlbereiche</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {[1, 2, 3, 4, 5, 6].map((wb) => {
                const gruppe = ortsbereicheImWahlbereich(wb, places);
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
          </div>}
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
            Ratslotse-Ortsbereiche, keine amtlichen Stadtteile · Grenzen: © OpenStreetMap-Mitwirkende · Wahlbereiche: Stadt Oldenburg
          </p>
        </div>
      )}
    </div>
  );
}

export function EntitiesTab() {
  // V-05: Aus der Mini-Karte einer KI-Antwort führt „Auf der Stadtkarte
  // öffnen" hierher — mit genau den Orten der zitierten Beschlüsse in `orte`
  // (Namen, komma-getrennt). Ohne den Parameter ändert sich nichts.
  const sp = useSearchParams();
  const router = useRouter();
  const orteFilter = useMemo(() => {
    const roh = sp.get("orte");
    if (!roh) return null;
    const namen = roh.split(",").map((n) => n.trim().toLowerCase()).filter(Boolean);
    return namen.length ? new Set(namen) : null;
  }, [sp]);
  const orteWeg = () => {
    const p = new URLSearchParams(sp.toString());
    p.delete("orte");
    router.replace(`/council?${p.toString()}`, { scroll: false });
  };
  const { data, loading } = useFetch<{ entities: Entity[] }>("/council/entities");
  const { data: geo, loading: geoLoading } = useFetch<{ entities: EntityMapPoint[] }>("/council/entities-map");
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<KindFilter>("");
  const [districts, setStadtteile] = useState<OrtsbereichFeature[]>([]);
  const [ortskatalog, setOrtskatalog] = useState<OrtsbereichEntry[]>([]);
  const [selectedST, setSelectedST] = useState<Set<string>>(new Set());
  useEffect(() => {
    void loadOrtsbereiche().then(setStadtteile);
    void loadOrtsbereichCatalog().then((catalog) => setOrtskatalog(catalog.places)).catch(() => {});
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
    if (districts.length) {
      for (const p of geo?.entities ?? []) m.set(p.slug, ortsbereichFor(p.lat, p.lon, districts));
    }
    return m;
  }, [geo, districts]);
  const stCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const st of pointST.values()) if (st) c[st] = (c[st] ?? 0) + 1;
    return c;
  }, [pointST]);

  // Punkte + Grenz-Overlays memoisiert — die Karte remountet sonst bei jedem
  // Tastendruck in der Suche (Array-Identität ist ihre Effect-Dependency).
  const points = useMemo(
    () => (geo?.entities ?? [])
      .filter((p) => (orteFilter ? orteFilter.has(p.name.toLowerCase()) : true))
      .filter((p) => (kind ? p.kind === kind : true))
      .filter((p) => (selectedST.size ? selectedST.has(pointST.get(p.slug) ?? "") : true)),
    [geo, kind, selectedST, pointST, orteFilter],
  );
  const outlines = useMemo(
    () => (selectedST.size ? districts.filter((f) => selectedST.has(f.properties.name)) : undefined),
    [districts, selectedST],
  );

  if (loading) return <div className="py-4"><TableSkeleton rows={8} cols={3} /></div>;
  if (all.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Themen" hint="Es wurden noch keine wiederkehrenden Eigennamen aus den Beschlüssen extrahiert." />;
  }

  const needle = q.trim().toLowerCase();
  const filtered = all
    .filter((e) => (orteFilter ? orteFilter.has(e.name.toLowerCase()) : true))
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
      {/* Sichtbar und abwählbar wie der Themen-Filter der Beschluss-Suche —
          sonst wüsste niemand, warum die Karte nur ein paar Pins zeigt. */}
      {orteFilter && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            Orte aus deiner Frage · {points.length === 1 ? "1 Ort" : `${points.length} Orte`}
            <button type="button" onClick={orteWeg} aria-label="Ortsfilter entfernen"
              className="rounded-full p-0.5 transition-colors hover:bg-primary/15">
              <X className="h-3 w-3" aria-hidden />
            </button>
          </span>
        </div>
      )}
      {/* Die Karte zuerst — sie ist der Blickfang der Seite, kein verstecktes
          Toggle-Feature. Kind-Chips unten filtern Karte UND Liste. Während der
          Geo-Fetch läuft, hält ein Platzhalter dieselbe Höhe (kein Pop-in-Shift). */}
      {geoLoading ? (
        <div className={cn(KARTE_RAHMEN, "flex items-center justify-center rounded-xl border border-border")}>
          <Spinner />
        </div>
      ) : (geo?.entities.length ?? 0) > 0 ? (
        // Hier bewusst KEIN `isolate`: Leaflets Panes (z bis ~700) fängt schon
        // `.leaflet-container` selbst ein (globals.css). Ein zweiter
        // Stapelkontext an dieser Stelle sperrte dagegen das Vollbild der Karte
        // in diesen Kasten — die Karte lag dann unter Topbar und Tab-Leiste,
        // ihr Schließen-Knopf verschwand dahinter, und vom Rest der Seite
        // stachen ausgerechnet die *positionierten* Teile durch: Suchfeld und
        // Stadtteil-Wähler schwebten mitten auf der Karte, Titel, Legende und
        // Art-Chips blieben unsichtbar (Tims iPad-Befund aus Build 11).
        <div className="relative">
          <CouncilMap points={points} outlines={outlines} className={cn(KARTE_RAHMEN, "rounded-xl")} />
          {/* Die Legende steht UNTER der Karte, nicht darin: Als Overlay unten
              links lag sie auf schmalen Displays über Leaflets Quellenangabe
              („OpenStreetMap, CARTO") — zwei Zeilen Text auf einer Zeile
              Nachweis, beides unlesbar. Darunter kann sie umbrechen, ohne
              etwas zu verdecken. „Punkt öffnet" statt „klicken öffnet":
              auf dem Telefon klickt niemand. */}
          <p className="mt-1.5 px-1 text-[11px] leading-relaxed text-muted-foreground">
            {selectedST.size > 0
              ? `${points.length} von ${geo!.entities.length} Punkten · ${selectedST.size} ${selectedST.size === 1 ? "Ortsbereich" : "Ortsbereiche"} ausgewählt`
              : `${points.length} verortete Themen und Beschlussorte · Punktgröße = Beschlüsse`}
            <span className="ml-2">Zahlenkreise bündeln nahe Orte</span>
            <span className="ml-2 inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-full" style={{ background: KIND_COLOR.beschlussort }} />
              Orange = konkreter Beschlussort
            </span>
          </p>
        </div>
      ) : null}

      {/* Suche + Kind-Filter (Farbpunkte = Kartenlegende) */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[14rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input data-search className="pl-9" placeholder="Thema suchen — z. B. Fliegerhorst"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {/* w-full auf Mobile: eigene, umbrechende Zeile. shrink-0 (früher hier)
            gab dem Container seine max-content-Breite — alle Chips in EINER
            Reihe —, was auf schmalen Screens über den Viewport lief. */}
        <div className="flex w-full flex-wrap gap-1.5 sm:w-auto">
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
          {districts.length > 0 && (geo?.entities.length ?? 0) > 0 && (
            <OrtsbereichFilter
              names={districts.map((f) => f.properties.name)}
              places={ortskatalog}
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
