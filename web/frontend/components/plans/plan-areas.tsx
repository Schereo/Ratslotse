"use client";

// GEBIETE AUS DEN KARTEN DES PLANS (council/plan_pages.py::_shape_places):
// je Art ein Kopf mit dem, was der Plan darunter versteht, darunter die
// Gebiete. Aufgeklappt steht, was der Plan zu einem Gebiet sagt —
// Kennzahlen (Kenndaten, Tabellen), Listen (Defizite, Handlungskonzept,
// Stärken, Schwächen) und seine Absätze als Zitat, je mit Seite.
//
// Eine Farbe für alle Arten: Die Karte unterscheidet sie am Rand
// (durchgezogen, gestrichelt, gepunktet, Strich-Punkt), nicht in der Farbe
// (DESIGNSPRACHE: Primärtönung, keine neue Kategorienfarbe).

import { Fragment } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import type { PlanPlace, PlanPlaces } from "@/lib/plans";
import { cn } from "@/lib/utils";

type Area = PlanPlace["areas"][number];
type Group = PlanPlaces["groups"][number];

/** Randstil je Art auf der Karte — Leaflet `dashArray`; Index wie `groups[].style` vom Backend. */
export const AREA_DASH: readonly (string | undefined)[] = [undefined, "7 5", "2 4", "9 4 2 4"];
/** Dieselben Muster, verkleinert für das Kästchen in Legende und Kopf. */
const SWATCH_DASH: readonly (string | undefined)[] = [undefined, "3.5 2.5", "1 2", "4 2 1 2"];

function hectares(v: number): string {
  return `${v.toLocaleString("de-DE", { maximumFractionDigits: 1 })} ha`;
}

/** Kästchen für eine Art: Fläche mit ihrem Randstil — oder ein Punkt, wo die Art nur Standorte hat. */
export function AreaSwatch({ style, site }: { style: number; site: boolean }) {
  if (site) return <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-full border-2 border-white bg-primary shadow" />;
  return (
    <svg aria-hidden width="18" height="12" viewBox="0 0 18 12" className="shrink-0 text-primary">
      <rect x="1" y="1" width="16" height="10" rx="2" fill="currentColor" fillOpacity="0.2" stroke="currentColor"
        strokeWidth="2" strokeDasharray={SWATCH_DASH[style % SWATCH_DASH.length]} />
    </svg>
  );
}

/** Die Zeile unter dem Namen: Fläche, Fläche laut Plan, und was der Plan in einer Zeile sagt. */
function subline(a: Area): string {
  const parts = [
    a.area_ha != null ? hectares(a.area_ha) : a.summary ? null : "Standort",
    a.area_ha_plan ? `laut Plan ${hectares(a.area_ha_plan)}` : null,
    a.summary,
  ];
  return parts.filter(Boolean).join(" · ");
}

function PageLink({ url, page }: { url: string | null; page: number | null }) {
  if (!url || !page) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-medium text-primary hover:underline">
      S. {page} <ExternalLink className="h-3 w-3" aria-hidden />
    </a>
  );
}

function AreaDetails({ area }: { area: Area }) {
  // Kennzahlen stehen fast immer auf einer Seite — die Fundstelle einmal darunter, nicht an jeder Zeile; und
  // gar nicht, wo es die Seite ist, auf die die Zeile schon zeigt.
  const pages = [...new Map(area.facts.filter((f) => f.page && f.source_url && f.page !== area.page)
    .map((f) => [f.page, f.source_url])).entries()];
  return (
    <div className="space-y-3 px-2 pb-3 pt-0.5">
      {area.facts.length > 0 && (
        <div>
          <dl className="grid gap-x-4 gap-y-1 text-[13px] leading-snug sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
            {area.facts.map((f) => (
              <Fragment key={f.label}>
                <dt className="text-muted-foreground">{f.label}</dt>
                <dd className="break-words text-foreground">{f.value}</dd>
              </Fragment>
            ))}
          </dl>
          {pages.length > 0 && (
            <p className="mt-1 flex flex-wrap gap-x-2 text-meta text-muted-foreground">
              Im Plan: {pages.map(([page, url]) => <PageLink key={page} url={url} page={page} />)}
            </p>
          )}
        </div>
      )}
      {area.notes.map((n) => (
        <div key={n.title}>
          <p className="flex flex-wrap items-baseline gap-x-1.5 text-meta font-medium text-muted-foreground">
            {n.title}{n.source_url && <span aria-hidden>·</span>}<PageLink url={n.source_url} page={n.page} />
          </p>
          {n.kind === "list" ? (
            <ul className="mt-1 max-w-[76ch] list-disc space-y-0.5 pl-5 text-[13.5px] leading-snug text-foreground">
              {n.items.map((item) => <li key={item} className="break-words">{item}</li>)}
            </ul>
          ) : (
            // Absätze des Plans: ruhiger als das markierte Zitat — ein Maßnahmenblatt hat leicht 2.000 Zeichen.
            <div className="mt-1 max-w-[76ch] space-y-2 border-l-2 border-border pl-3 text-[13.5px] leading-relaxed text-foreground/90">
              {n.items.map((text) => <p key={text}>„{text}“</p>)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function AreaRow({ place, open, onToggle, columns }: { place: PlanPlace; open: boolean; onToggle: () => void; columns: boolean }) {
  const a = place.areas[0];
  const details = a.facts.length > 0 || a.notes.length > 0;
  return (
    <li id={`plan-place-${place.slug}`} className={cn("min-w-0 rounded-md", columns && "@3xl:border-b @3xl:border-border/70", open && "bg-primary/[0.06]")}>
      <div className="flex items-start gap-2">
        <button type="button" onClick={onToggle} aria-pressed={open} aria-expanded={details ? open : undefined}
          className="flex min-h-11 min-w-0 flex-1 items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-primary/[0.04]">
          <span className="min-w-0 flex-1">
            {/* „Ziegelhofviertel/Haareneschviertel“ hat keine Trennstelle — bei 320 px schob es die Seite. */}
            <span className="block text-[14px] font-medium leading-snug text-foreground [overflow-wrap:anywhere]">{place.name}</span>
            <span className="mt-0.5 block text-meta text-muted-foreground [overflow-wrap:anywhere]">{subline(a)}</span>
          </span>
          {details && (
            <ChevronDown className={cn("mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
          )}
        </button>
        <a href={a.source_url} target="_blank" rel="noreferrer"
          className="mt-2 inline-flex shrink-0 items-center gap-1 whitespace-nowrap pr-2 text-meta font-medium text-primary hover:underline">
          {a.source_label} <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>
      {open && details && <AreaDetails area={a} />}
    </li>
  );
}

/** Die Gebiete, nach Art in der Reihenfolge des Plans; `total`: Zahl je Art über alle (auch eingeklappte). */
export function AreaList({ items, groups, total, focus, onFocus, columns }: {
  items: readonly PlanPlace[];
  groups: readonly Group[];
  total: ReadonlyMap<string, number>;
  focus: string | null;
  onFocus: (slug: string | null) => void;
  columns: boolean;
}) {
  const info = new Map(groups.map((g) => [g.name, g]));
  const ordered = new Map<string, PlanPlace[]>();
  for (const p of items) ordered.set(p.areas[0].group, [...(ordered.get(p.areas[0].group) ?? []), p]);
  return (
    <>
      {[...ordered.entries()].map(([name, list]) => {
        const g = info.get(name);
        return (
          <div key={name} className="mt-2">
            <div className="px-2">
              <p className="flex items-center gap-1.5 text-meta font-medium text-foreground/80">
                <AreaSwatch style={g?.style ?? 0} site={g?.sites_only ?? false} />
                {name}{total.size > 1 ? ` · ${total.get(name) ?? list.length}` : ""}
              </p>
              {g?.description && (
                <p className="mt-0.5 max-w-[76ch] text-meta text-muted-foreground">
                  {g.description} <PageLink url={g.source_url} page={g.page} />
                </p>
              )}
            </div>
            <ul className={cn("mt-1 grid gap-x-6 divide-y divide-border/70", columns && "@3xl:grid-cols-2 @3xl:divide-y-0")}>
              {list.map((place) => (
                <AreaRow key={place.slug} place={place} open={focus === place.slug} columns={columns}
                  onToggle={() => onFocus(focus === place.slug ? null : place.slug)} />
              ))}
            </ul>
          </div>
        );
      })}
    </>
  );
}
