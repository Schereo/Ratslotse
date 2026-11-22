"use client";

// AUS DEM PLAN: Tabellen, die der Plan selbst enthält — die Rangfolge der
// Lärm-Schwerpunkte, die Wärmenetzeignungsgebiete (council/plan_pages.py::
// lists_block). Zeile für Zeile, wie sie im Dokument stehen, mit der Seite.
// Bis drei Spalten bleibt es auch schmal eine Tabelle; breitere Tabellen
// stapeln sich schmal zu einer Liste, damit nichts seitwärts scrollt.

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Kicker } from "@/components/plans/parts";
import type { PlanDetail } from "@/lib/plans";
import { cn } from "@/lib/utils";

type PlanList = PlanDetail["lists"][number];

/** So viele Zeilen stehen offen; der Rest hinter „alle zeigen“ — aber nur, wo
 *  dahinter genug wartet: Eine einzelne verborgene Zeile wäre ein Klick für nichts. */
const VISIBLE = 10;
const HIDE_AT_LEAST = 4;

function SourceLink({ href, page, className }: { href: string; page: number; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer"
      className={cn("inline-flex items-center gap-1 whitespace-nowrap font-medium text-primary hover:underline", className)}>
      S. {page} <ExternalLink className="h-3 w-3" aria-hidden />
    </a>
  );
}

function Table({ list }: { list: PlanList }) {
  const [showAll, setShowAll] = useState(false);
  const folds = list.rows.length >= VISIBLE + HIDE_AT_LEAST;
  const rows = showAll || !folds ? list.rows : list.rows.slice(0, VISIBLE);
  const withPages = list.rows.some((r) => r.page);
  const narrowTable = list.columns.length <= 3;
  return (
    <div>
      <table className={cn("w-full border-collapse text-[13.5px]", !narrowTable && "hidden @xl:table")}>
        <thead>
          <tr className="border-b border-border text-left text-meta text-muted-foreground">
            {list.columns.map((c) => <th key={c} scope="col" className="py-1.5 pr-3 font-medium">{c}</th>)}
            {withPages && <th scope="col" className="py-1.5 font-medium">Im Plan</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/70">
          {rows.map((r) => (
            <tr key={r.cells.join("|")}>
              {r.cells.map((cell, i) => (
                <td key={i} className={cn("py-1.5 pr-3 align-top", i === 0 ? "font-mono text-meta text-muted-foreground" : "text-foreground",
                  /^\d/.test(cell) && i > 0 && "tabular-nums")}>{cell}</td>
              ))}
              {withPages && <td className="py-1.5 align-top text-meta">{r.page && r.source_url && <SourceLink href={r.source_url} page={r.page} />}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      {!narrowTable && (
        <ul className="divide-y divide-border/70 @xl:hidden">
          {rows.map((r) => (
            <li key={r.cells.join("|")} className="py-2">
              <p className="text-[14px] font-medium leading-snug text-foreground">
                <span className="font-mono text-meta font-normal text-muted-foreground">{r.cells[0]}</span> {r.cells[list.name_column]}
              </p>
              <dl className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-meta text-muted-foreground">
                {r.cells.map((cell, i) => (i === 0 || i === list.name_column ? null : (
                  <div key={i} className="inline-flex gap-1"><dt>{list.columns[i]}:</dt><dd className="text-foreground tabular-nums">{cell}</dd></div>
                )))}
                {r.page && r.source_url && <div><SourceLink href={r.source_url} page={r.page} /></div>}
              </dl>
            </li>
          ))}
        </ul>
      )}
      {folds && (
        <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
          className="mt-1 inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-primary hover:underline">
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-weg ease-in-out-strong", showAll && "rotate-180")} aria-hidden />
          {showAll ? "Weniger zeigen" : `Alle ${list.rows.length} zeigen`}
        </button>
      )}
    </div>
  );
}

export function PlanLists({ lists }: { lists: PlanList[] }) {
  if (!lists.length) return null;
  return (
    <section aria-labelledby="plan-lists" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-lists">Aus dem Plan</span></Kicker>
      <div className="mt-2 flex flex-col gap-5">
        {lists.map((list) => (
          <div key={list.key} className="min-w-0">
            <h3 className="text-[15px] font-semibold leading-snug text-foreground">{list.title}</h3>
            <p className="mb-1.5 mt-0.5 text-meta text-muted-foreground">
              {list.caption} · <SourceLink href={list.source_url} page={list.page} />
            </p>
            <Table list={list} />
          </div>
        ))}
      </div>
    </section>
  );
}
