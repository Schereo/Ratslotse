"use client";

// KARTE: wo der Plan etwas vorsieht oder wo Beschlüsse zu ihm etwas
// festgelegt haben (council/plan_pages.py::places_block). Vier Quellen:
// Gebiete, nachgezeichnet aus den Karten des Plans (Wärmeplan, Ruhige
// Gebiete, Masterplan Stadtgrün, Spielleitplanung; beim Einzelhandelskonzept
// auch Standorte als Punkt), Abschnitte,
// die der Plan selbst festlegt (Lärmaktionsplan, mit seinem Vorschlag und
// der Seite), Straßen und Plätze, die ein Maßnahmentitel beim
// Namen nennt (von Hand durchgesehen), und Orte, die die Ortszuordnung der
// Ratsdaten den Umsetzungs- und Berichtsbeschlüssen schon gegeben hat. Unter
// drei Orten gibt es keine Karte.

import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Kicker, StatusChip } from "@/components/plans/parts";
import { AreaList, AreaSwatch } from "@/components/plans/plan-areas";
import { Quote } from "@/components/plans/quoted";
import { decisionHref } from "@/lib/routes";
import { apiUrl } from "@/lib/api";
import { formatDate, type PlanPlace, type PlanPlaces } from "@/lib/plans";
import { cn } from "@/lib/utils";

const PlanMap = dynamic(() => import("@/components/plans/plan-map"), {
  ssr: false,
  loading: () => <div className="h-72 w-full animate-pulse rounded-xl bg-muted sm:h-96" />,
});

/** So viele Zeilen stehen offen; der Rest hinter „alle zeigen“. */
const VISIBLE = 8;
/** Gebiete: so viele je Art offen — es sei denn, es wären nur zwei mehr (dann alle, statt zwei hinter einem
 *  Knopf). Je Art, nicht insgesamt: Sonst verschwänden die sechs geplanten Spielplätze hinter 26 Suchräumen. */
const GROUP_VISIBLE = 6;

function hectares(v: number): string {
  return `${v.toLocaleString("de-DE", { maximumFractionDigits: 1 })} ha`;
}

/** Die Gebiete nach ihrer Art laut Legende („Friedhof“, „Ruhiges Gebiet“), in der Reihenfolge des Plans. */
function byGroup(items: readonly PlanPlace[]): [string, PlanPlace[]][] {
  const out = new Map<string, PlanPlace[]>();
  for (const p of items) {
    const g = p.areas[0].group;
    out.set(g, [...(out.get(g) ?? []), p]);
  }
  return [...out.entries()];
}

function areaCount(items: readonly PlanPlace[]): string {
  const sites = items.filter((p) => !p.geometry).length;
  const areas = items.length - sites;
  if (!sites) return `${areas} Gebiete`;
  if (!areas) return `${sites} Standorte`;
  return `${areas} Gebiete, ${sites} Standorte`;
}

export function Places({ places, planKey }: { places: PlanPlaces; planKey: string }) {
  const [focus, setFocus] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [allAreas, setAllAreas] = useState(false);
  const fromAreas = places.items.filter((p) => p.areas.length > 0);
  const fromSections = places.items.filter((p) => p.sections.length > 0);
  const fromMeasures = places.items.filter((p) => p.measures.length > 0);
  const fromDecisions = places.items.filter((p) => p.measures.length === 0 && p.sections.length === 0 && p.areas.length === 0);
  // Zwei Spalten nur, wo zwei Listen nebeneinander stehen — sonst bliebe rechts ein Loch.
  const groups = [fromAreas, fromSections, fromMeasures, fromDecisions].filter((g) => g.length > 0).length;
  const areaGroups = byGroup(fromAreas);
  const folded = areaGroups.flatMap(([, list]) => (list.length > GROUP_VISIBLE + 2 ? list.slice(0, GROUP_VISIBLE) : list));
  const areasFold = folded.length < fromAreas.length;
  const visibleAreas = allAreas || !areasFold ? fromAreas : folded;
  const groupSize = new Map(areaGroups.map(([g, items]) => [g, items.length]));
  // Gebiete in zwei Spalten nur, wo sie die ganze Breite haben.
  const areaColumns = groups === 1;
  const shown = showAll ? fromDecisions : fromDecisions.slice(0, VISIBLE);
  const pick = (slug: string) => {
    setFocus(slug);
    // Ein Gebiet hinter „alle zeigen“: erst aufklappen, dann hinscrollen.
    const hidden = !allAreas && areasFold && fromAreas.some((p) => p.slug === slug) && !folded.some((p) => p.slug === slug);
    if (hidden) setAllAreas(true);
    const scroll = () => document.getElementById(`plan-place-${slug}`)?.scrollIntoView({ block: "nearest" });
    if (hidden) window.setTimeout(scroll, 50);
    else scroll();
  };
  const row = "flex w-full min-h-11 items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-primary/[0.04]";
  return (
    <section aria-labelledby="plan-places" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-places">Karte</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">
          {fromAreas.length === places.items.length ? areaCount(fromAreas) : `${places.items.length} Orte`}
        </p>
      </div>
      <p className="mb-3 max-w-[76ch] text-hinweis text-muted-foreground">{places.note}</p>
      <PlanMap places={places.items} groups={places.groups} focus={focus} onPick={pick} />
      <ul aria-label="Legende" className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-meta text-muted-foreground">
        {/* Je Art ein Eintrag mit dem Wort des Plans — „Gebiet aus dem Plan“ sagte nicht, was es ist. */}
        {places.groups.map((g) => (
          <li key={g.name} className="inline-flex items-center gap-1.5"><AreaSwatch style={g.style} site={g.sites_only} /> {g.name}</li>
        ))}
        {fromSections.length > 0 && (
          <li className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-1 w-5 rounded-full bg-primary" /> Abschnitt aus dem Plan</li>
        )}
        {fromMeasures.some((p) => p.geometry) && (
          <li className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-1 w-5 rounded-full bg-primary" /> Straße einer Maßnahme</li>
        )}
        {fromMeasures.some((p) => !p.geometry) && (
          <li className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full border-2 border-white bg-primary shadow" /> Ort einer Maßnahme</li>
        )}
        {fromDecisions.length > 0 && (
          <li className="inline-flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full border-2 border-white bg-signal shadow" /> Ort aus einem Beschluss</li>
        )}
      </ul>
      {places.geojson && (
        <p className="mt-1.5 text-meta">
          <a href={apiUrl(`/council/plan/${planKey}/geojson`)} download={`${planKey}.geojson`}
            className="inline-flex min-h-11 items-center gap-1 font-medium text-primary hover:underline sm:min-h-0">
            Als GeoJSON herunterladen
          </a>
        </p>
      )}
      <div className={cn("mt-4 grid gap-5", groups > 1 && "@3xl:grid-cols-2")}>
        {fromSections.length > 0 && (
          <div className="min-w-0">
            <Kicker>Aus dem Plan · {fromSections.length} Abschnitte</Kicker>
            <ul className="mt-1 divide-y divide-border/70">
              {fromSections.map((place) => {
                const s = place.sections[0];
                const open = focus === place.slug;
                return (
                  <li key={place.slug} id={`plan-place-${place.slug}`} className={cn("rounded-md", open && "bg-primary/[0.06]")}>
                    <button type="button" onClick={() => setFocus(open ? null : place.slug)} aria-pressed={open} aria-expanded={open} className={row}>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-medium leading-snug text-foreground">{place.name}</span>
                        <span className="mt-0.5 block break-words text-meta text-muted-foreground">
                          <span className="font-mono">{s.code}</span> · {s.stretch}
                        </span>
                      </span>
                      <ChevronDown className={cn("mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
                    </button>
                    {open && (
                      <div className="px-2 pb-2.5">
                        <Quote text={s.quote} className="max-w-[76ch] text-[13.5px]" />
                        <a href={s.source_url} target="_blank" rel="noreferrer"
                          className="mt-1.5 inline-flex min-h-11 items-center gap-1 text-meta font-medium text-primary hover:underline sm:min-h-0">
                          Seite {s.page} im Plan <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {fromAreas.length > 0 && (
          <div className="min-w-0">
            <Kicker>Aus den Karten des Plans · {areaCount(fromAreas)}</Kicker>
            <AreaList items={visibleAreas} groups={places.groups} total={groupSize} focus={focus} onFocus={setFocus} columns={areaColumns} />
            {areasFold && (
              <button type="button" onClick={() => setAllAreas((v) => !v)} aria-expanded={allAreas}
                className="mt-1 inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-primary hover:underline">
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-weg ease-in-out-strong", allAreas && "rotate-180")} aria-hidden />
                {allAreas ? "Weniger zeigen" : `Alle ${fromAreas.length} zeigen`}
              </button>
            )}
          </div>
        )}
        {fromMeasures.length > 0 && (
          <div className="min-w-0">
            <Kicker>Aus der Maßnahmenliste · {places.measures_named}{places.measures_total ? ` von ${places.measures_total}` : ""} Maßnahmen</Kicker>
            <ul className="mt-1 divide-y divide-border/70">
              {fromMeasures.map((place) => (
                <li key={place.slug} id={`plan-place-${place.slug}`}>
                  <button type="button" onClick={() => setFocus(place.slug)} aria-pressed={focus === place.slug}
                    className={cn(row, focus === place.slug && "bg-primary/[0.06]")}>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium leading-snug text-foreground">{place.name}</span>
                      {place.measures.map((m) => (
                        <span key={m.code} className="mt-0.5 block break-words text-meta text-muted-foreground">
                          <span className="font-mono">{m.code}</span> · {m.title}
                          {m.status_raw && <StatusChip raw={m.status_raw} norm={m.status_norm} className="ml-1.5 align-[1px]" />}
                        </span>
                      ))}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {fromDecisions.length > 0 && (
          <div className="min-w-0">
            <Kicker>Aus Beschlüssen zum Plan · {fromDecisions.length} Orte</Kicker>
            <ul className="mt-1 divide-y divide-border/70">
              {shown.map((place) => (
                <li key={place.slug} id={`plan-place-${place.slug}`} className={cn("rounded-md", focus === place.slug && "bg-primary/[0.06]")}>
                  <button type="button" onClick={() => setFocus(place.slug)} aria-pressed={focus === place.slug} className={row}>
                    <span className="min-w-0 flex-1 text-[14px] font-medium leading-snug text-foreground">{place.name}</span>
                    {place.decision_count > 1 && <span className="font-mono text-meta text-muted-foreground">{place.decision_count} Beschlüsse</span>}
                  </button>
                  {/* Der jüngste Beschluss genügt als Weg; die übrigen tragen oft denselben Titel. */}
                  {place.decisions[0] && (
                    <p className="-mt-1 pb-1.5 pl-2 text-meta text-muted-foreground">
                      <span className="font-mono">{formatDate(place.decisions[0].date)}</span>{" · "}
                      <Link href={decisionHref(place.decisions[0].id)} prefetch={false} className="break-words text-primary hover:underline">
                        {place.decisions[0].title}
                      </Link>
                    </p>
                  )}
                </li>
              ))}
            </ul>
            {fromDecisions.length > VISIBLE && (
              <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
                className="mt-1 inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-primary hover:underline">
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-weg ease-in-out-strong", showAll && "rotate-180")} aria-hidden />
                {showAll ? "Weniger zeigen" : `Alle ${fromDecisions.length} Orte zeigen`}
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
