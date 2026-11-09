"use client";

// MASSNAHMEN: die geprüfte Liste eines Plans (council/plan_measures/*.json).
//
// Jedes Handlungsfeld trägt seine Maßnahmen als Kästchen in der Kopfzeile: ein
// Kästchen je Maßnahme, die Pakete leicht abgesetzt. Man sieht, woraus der
// Plan besteht und wo sein Gewicht liegt, bevor man eine Zeile gelesen hat —
// die Liste ist ihr eigenes Bild, ohne dass darüber noch eines stünde.
//
// Wo die Stadt einen Stand je Maßnahme meldet, tragen die Kästchen ihn als
// Farbton und die Zeile das Wort der Stadt. Wo nicht, sind alle gleich
// getönt: Dann sagt das Bild nur, WAS vorgesehen ist — nichts darüber, was
// daraus wurde. Ein Kästchen ohne Stand ist gestrichelt, nicht „offen“.

import { useMemo, useState } from "react";
import { ChevronDown, ExternalLink, Search, X } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Kicker, STATUS_SQUARE, StatusChip } from "@/components/plans/parts";
import { Input } from "@/components/ui";
import { byPackage, filterMeasures, type PlanMeasure, type PlanMeasureField, type PlanMeasures } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** Bis zu so vielen Maßnahmen stehen alle Handlungsfelder offen. */
const OPEN_UP_TO = 20;
/** Ab so vielen lohnt die Suche. */
const SEARCH_FROM = 25;

const fieldName = (field: PlanMeasureField) => field.field ?? "Maßnahmen";

/** Die Maßnahmen eines Felds als Kästchen, an den Paketgrenzen abgesetzt. */
function Squares({ measures, tinted }: { measures: readonly PlanMeasure[]; tinted: boolean }) {
  return (
    <span aria-hidden className="flex flex-wrap gap-x-[7px] gap-y-[3px]">
      {byPackage(measures).map((pkg, i) => (
        <span key={`${pkg.name}-${i}`} className="flex flex-wrap gap-[3px]">
          {pkg.measures.map((m) => (
            <span key={m.code} title={[m.code, m.title, m.status_raw].filter(Boolean).join(" · ")}
              className={cn("h-3 w-3 rounded-[3px] border", tinted ? STATUS_SQUARE[m.status_norm ?? "none"] : "border-primary/40 bg-primary/15")} />
          ))}
        </span>
      ))}
    </span>
  );
}

function Rows({ measures }: { measures: readonly PlanMeasure[] }) {
  return (
    // Ein Raster je Feld: Die Kennungsspalte ist so breit wie die längste
    // Kennung („K1“ wie „Klimapakt_07“), der Titel nimmt den Rest.
    <ul className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 pb-3">
      {byPackage(measures).map((pkg, i) => (
        <li key={`${pkg.name}-${i}`} className="col-span-2 grid grid-cols-subgrid">
          {pkg.name && (
            <p className="col-span-2 mt-2 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">{pkg.name}</p>
          )}
          <ul className="col-span-2 grid grid-cols-subgrid">
            {pkg.measures.map((m) => (
              <li key={m.code} className="col-span-2 grid grid-cols-subgrid">
                <span className="py-1 font-mono text-meta text-muted-foreground">{m.code}</span>
                <span className="break-words py-1 text-[14px] leading-snug text-foreground">
                  {m.title}
                  {m.status_raw && <StatusChip raw={m.status_raw} norm={m.status_norm} className="ml-2 align-[1px]" />}
                </span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

export function Measures({ measures }: { measures: PlanMeasures }) {
  const names = measures.groups.map(fieldName);
  const [open, setOpen] = useState<Set<string>>(() => new Set(measures.count <= OPEN_UP_TO ? names : []));
  const [query, setQuery] = useState("");
  const searching = query.trim().length > 0;
  const filtered = useMemo(() => filterMeasures(measures.groups, query), [measures.groups, query]);
  const hits = filtered.reduce((n, field) => n + field.measures.length, 0);
  const allOpen = open.size === names.length;

  const toggle = (name: string) => setOpen((before) => {
    const next = new Set(before);
    if (next.has(name)) next.delete(name); else next.add(name);
    return next;
  });
  const listDate = measures.source.as_of_label ? `Liste vom ${measures.source.as_of_label}` : undefined;

  return (
    <section aria-labelledby="plan-measures" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-measures">Maßnahmen</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">{[`${measures.count}`, listDate].filter(Boolean).join(" · ")}</p>
      </div>
      {measures.count_note && <p className="mb-3 max-w-[76ch] text-hinweis text-muted-foreground">{measures.count_note}</p>}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {measures.count >= SEARCH_FROM && (
          <div className="relative min-w-0 flex-1 basis-56">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
              aria-label="In den Maßnahmen suchen" placeholder={`In ${measures.count} Maßnahmen suchen`}
              className="pl-9 pr-9 [&::-webkit-search-cancel-button]:hidden" />
            {searching && (
              <button type="button" onClick={() => setQuery("")} aria-label="Suche leeren"
                className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
        )}
        {searching ? (
          <p role="status" className="font-mono text-meta text-muted-foreground">{hits} von {measures.count}</p>
        ) : measures.groups.length > 1 && (
          <button type="button" onClick={() => setOpen(new Set(allOpen ? [] : names))}
            className="min-h-11 text-meta font-medium text-primary hover:underline">
            {allOpen ? "Alle zuklappen" : "Alle aufklappen"}
          </button>
        )}
      </div>
      {searching && hits === 0 ? (
        <p className="mt-3 rounded-xl border border-dashed border-border px-3.5 py-3 text-hinweis text-muted-foreground">
          Keine Maßnahme passt zu „{query.trim()}“. Gesucht wird in Kennung, Titel und Handlungsfeld.
        </p>
      ) : (
        <div className="mt-2 divide-y divide-border/70 border-y border-border/70">
          {filtered.map((field) => {
            const name = fieldName(field);
            const isOpen = searching || open.has(name);
            return (
              <div key={name}>
                {/* Name · Kästchen · Zahl. Schmal rutschen die Kästchen unter den Namen. */}
                <button type="button" onClick={() => toggle(name)} aria-expanded={isOpen} disabled={searching}
                  className="grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 py-2.5 text-left hover:bg-primary/[0.03] disabled:cursor-default disabled:hover:bg-transparent @xl:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_auto]">
                  <span className="min-w-0 break-words text-[14px] font-semibold leading-snug text-foreground">{name}</span>
                  <span className="col-span-2 row-start-2 min-w-0 @xl:col-span-1 @xl:col-start-2 @xl:row-start-1">
                    <Squares measures={field.measures} tinted={measures.status_count > 0} />
                  </span>
                  <span className="col-start-2 row-start-1 flex items-center gap-2 @xl:col-start-3">
                    <span className="font-mono text-meta text-muted-foreground">{field.measures.length}</span>
                    {!searching && (
                      <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-weg ease-in-out-strong", isOpen && "rotate-180")} aria-hidden />
                    )}
                  </span>
                </button>
                <Aufklapp offen={isOpen}><Rows measures={field.measures} /></Aufklapp>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-meta text-muted-foreground">
        {measures.status_count > 0 ? (
          <>
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden className={cn("h-3 w-3 rounded-[3px] border", STATUS_SQUARE.in_progress)} /> Stand laut Stadt
              {measures.status_as_of_label && `, ${measures.status_as_of_label}`}
            </span>
            {measures.status_count < measures.count && (
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className={cn("h-3 w-3 rounded-[3px] border", STATUS_SQUARE.none)} /> kein Stand genannt
              </span>
            )}
          </>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-3 w-3 rounded-[3px] border border-primary/40 bg-primary/15" /> eine Maßnahme
          </span>
        )}
        <span>
          Quelle:{" "}
          <a href={measures.source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {measures.source.label}
            <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px" aria-hidden />
          </a>
          {measures.source.template_number && <span className="font-mono"> · {measures.source.template_number}</span>}
        </span>
      </p>
    </section>
  );
}
