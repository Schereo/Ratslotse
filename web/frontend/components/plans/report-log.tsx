"use client";

// BERICHTE IM RAT: der Zeitstrahl eines Plans, das jüngste Jahr zuerst.
//
// Grammatik wie der Zeitstrahl RG-03 (DESIGNSPRACHE § 5): Schiene, 10-px-Punkte,
// die jüngste Station gefüllt mit Halo und „Aktueller Stand“. Neu sind die
// Jahre als Zwischenzeilen — und dass auch die Jahre dastehen, in denen NICHTS
// zu finden war: gestrichelt, wie jede Pause („noch nicht“, § 4). Die Lücke ist
// eine Aussage über den Bestand, nie über die Arbeit (Plan § 3.3a); welche
// Jahre als Lücke zählen, rechnet das Backend (council/plan_pages.py::year_log).
//
// Jüngstes zuerst, anders als die Akte-Zeitleiste: Wer hierher kommt, fragt
// „Was ist der Stand?“ — die Chronologie von links nach rechts zeigt schon das
// Zeitband in der Kopfbühne.

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, CircleDashed } from "lucide-react";
import { AdoptionBadge, Kicker } from "@/components/plans/parts";
import { QuotedLine } from "@/components/plans/quoted";
import { STAFFEL, staffelStil } from "@/components/staffel";
import { decisionHref } from "@/lib/routes";
import {
  committeeList, formatDate, reportCount, stationKind, yearSpan,
  type PlanDetail, type PlanLogEntry, type PlanNews, type PlanStation,
} from "@/lib/plans";
import { cn } from "@/lib/utils";

/** So viele Stationen stehen mindestens offen; ein Jahr wird nie zerschnitten. */
const VISIBLE = 6;

function Dot({ station, current }: { station: PlanStation; current: boolean }) {
  const isDecision = station.kind === "adoption" || station.kind === "amendment";
  return (
    <span className={cn("mt-1 h-2.5 w-2.5 shrink-0 border-2",
      isDecision ? "rounded-[3px]" : "rounded-full",
      current ? "border-primary bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
        : station.kind === "preparation" ? "border-muted-foreground/40 bg-muted"
        : isDecision ? "border-primary bg-primary"
        : station.oral ? "border-primary/60 bg-card"
        : "border-primary bg-primary/25")} />
  );
}

function Station({ station, index, current, currentLabel, last, highlighted }: {
  station: PlanStation; index: number; current: boolean; currentLabel: string; last: boolean; highlighted: boolean;
}) {
  const until = station.date_end ? ` – ${formatDate(station.date_end)}` : "";
  return (
    <li id={`station-${index}`} className="flex scroll-mt-24 gap-3">
      <div className="flex w-4 shrink-0 flex-col items-center">
        <Dot station={station} current={current} />
        {!last && <span className="mt-1 w-0 flex-1 border-l-2 border-primary/25" />}
      </div>
      {/* Schmal untereinander; in einer breiten Karte steht das Datum als eigene
          Spalte davor — die Tage liegen dann untereinander wie in einem Journal.
          Jede Zeile trägt denselben Innenrand wie der getönte Kasten des Stands — sonst
          stünde dessen Titel 12 px weiter rechts als alle anderen. Die Markierung nach
          einem Sprung tönt nur; ihre Maße ergeben zusammen dieselbe Höhe wie vorher. */}
      <div className={cn("min-w-0 flex-1 rounded-lg px-3 transition-colors duration-buehne ease-out-strong @2xl:grid @2xl:grid-cols-[13.5rem_minmax(0,1fr)] @2xl:gap-x-4",
        current ? "mb-3 bg-primary/[0.06] py-2.5" : highlighted ? "-mt-1.5 mb-1.5 bg-primary/[0.08] pb-2.5 pt-1.5" : "pb-4",
        highlighted && current && "bg-primary/[0.12]")}>
        <div className="min-w-0">
          {current && <p className="mb-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-primary">{currentLabel}</p>}
          <p className="font-mono text-[10.5px] uppercase leading-relaxed tracking-[0.08em] text-muted-foreground">
            <span className="@2xl:block @2xl:text-[12px] @2xl:text-foreground">{formatDate(station.date)}{until}</span>
            <span className="@2xl:hidden"> · </span>
            <span className="@2xl:block">{stationKind(station)}</span>
          </p>
        </div>
        <div className="min-w-0">
          <p className="mt-0.5 break-words text-quelle font-medium leading-snug text-foreground @2xl:mt-0">
            {station.decision_id != null ? (
              <Link href={decisionHref(station.decision_id)} className="hover:text-primary hover:underline">{station.title}</Link>
            ) : station.title}
          </p>
          {station.label && <p className="mt-0.5 break-words text-hinweis text-foreground">{station.label}</p>}
          {/* Der Titel sagt selten, was drinsteht — der Satz schon. Selbstauskunft der Verwaltung, als solche benannt. */}
          {station.summary && (
            <QuotedLine text={station.summary.text} quote={station.summary.quote} label="Laut Bericht" tinted={current || highlighted} className="mt-1" />
          )}
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted-foreground">
            {station.kind === "adoption" && station.mode && <AdoptionBadge mode={station.mode} />}
            <span>
              {committeeList(station.committees)}
              {station.template_number && <span className="font-mono"> · {station.template_number}</span>}
              {station.members.length > 1 && <span> · {station.members.length} Beratungen</span>}
            </span>
          </p>
        </div>
      </div>
    </li>
  );
}

/** Das Jahr als Zwischenzeile über seinen Stationen — mit einer Haarlinie,
 *  die bei einer Lücke gestrichelt ist. Eine Spalte davor nähme den Titeln
 *  auf dem Handy ein Fünftel der Breite. */
function YearHeading({ entry }: { entry: PlanLogEntry }) {
  return (
    <p className="mb-2 flex items-center gap-2.5 font-mono text-[12px] font-medium tabular-nums text-foreground">
      {yearSpan(entry)}
      <span aria-hidden className={cn("h-0 flex-1 border-t", entry.kind === "gap" ? "border-dashed border-muted-foreground/50" : "border-border")} />
    </p>
  );
}

function LogSection({ entry, stations, currentIndex, currentLabel, highlighted, row }: {
  entry: PlanLogEntry; stations: readonly PlanStation[]; currentIndex: number; currentLabel: string;
  highlighted: number | null; row: number;
}) {
  if (entry.kind === "gap") {
    return (
      <li className={cn(STAFFEL, "pb-3")} style={staffelStil(row)}>
        <YearHeading entry={entry} />
        <p className="flex items-start gap-3 text-hinweis italic text-muted-foreground">
          <span className="flex w-4 shrink-0 justify-center pt-[5px]"><CircleDashed className="h-3.5 w-3.5 not-italic" aria-hidden /></span>
          {entry.text}
        </p>
      </li>
    );
  }
  return (
    <li className={STAFFEL} style={staffelStil(row)}>
      <YearHeading entry={entry} />
      <ol className="flex flex-col">
        {entry.stations.map((index, j) => (
          <Station key={index} station={stations[index]} index={index} current={index === currentIndex}
            currentLabel={currentLabel} last={j === entry.stations.length - 1} highlighted={highlighted === index} />
        ))}
      </ol>
    </li>
  );
}

/** NEU IM JÜNGSTEN BERICHT: was dort steht und im vorigen Bericht derselben Reihe nicht. Gezeigt wird
 *  es nur, solange der Bericht wirklich der jüngste und nicht älter als zwei Jahre ist (Backend). */
function News({ news }: { news: PlanNews }) {
  return (
    <div className="mb-4 max-w-[76ch] rounded-xl border border-primary/15 bg-primary/[0.04] px-3.5 py-3">
      <Kicker className="text-primary">Neu im jüngsten Bericht · {news.to_date_label}</Kicker>
      <ul className="mt-1 divide-y divide-primary/10">
        {news.items.map((item) => (
          <li key={item.text}><QuotedLine text={item.text} quote={item.quote} tinted className="py-1" /></li>
        ))}
      </ul>
      <p className="mt-2 text-hinweis text-muted-foreground">
        Verglichen mit dem Bericht vom {news.from_date_label}. {news.note}
      </p>
    </div>
  );
}

export function ReportLog({ plan, target }: {
  plan: PlanDetail;
  /** Die Station, zu der das Zeitband springen will — `n` zählt hoch, damit derselbe Klick zweimal wirkt. */
  target: { station: number; n: number } | null;
}) {
  const { stations, log } = plan.timeline;
  const [showAll, setShowAll] = useState(false);
  const [highlighted, setHighlighted] = useState<number | null>(null);

  // Die jüngsten Jahre, bis genug Stationen dastehen; eine Lücke dazwischen bleibt sichtbar.
  let openCount = log.length;
  if (stations.length > VISIBLE + 2) {
    let n = 0;
    openCount = 0;
    for (const entry of log) {
      if (n >= VISIBLE && entry.kind === "year") break;
      n += entry.stations.length;
      openCount += 1;
    }
  }
  const hidden = showAll ? [] : log.slice(openCount);
  const hiddenStations = hidden.reduce((n, entry) => n + entry.stations.length, 0);
  const visible = showAll ? log : log.slice(0, openCount);

  useEffect(() => {
    if (!target) return;
    // Die Station steht vielleicht noch hinter „Frühere Jahre zeigen“: erst
    // aufklappen, gesprungen wird im Durchlauf danach — dann ist sie im DOM.
    if (!showAll) { setShowAll(true); return; }
    setHighlighted(target.station);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(`station-${target.station}`)
      ?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    const off = window.setTimeout(() => setHighlighted(null), 2400);
    return () => window.clearTimeout(off);
    // `showAll` gehört dazu: Der Sprung wartet auf das Aufklappen.
  }, [target, showAll]);

  const summary = stations.length === 0 ? undefined
    : plan.report_count > 0 ? `${reportCount(plan.report_count)} · ${plan.timeline.span}` : plan.timeline.span;
  return (
    <section aria-labelledby="plan-reports" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-reports">Berichte im Rat</span></Kicker>
        {summary && <p className="font-mono text-meta text-muted-foreground">{summary}</p>}
      </div>
      {plan.report_note && (
        // Gestrichelt = „noch nicht“. Kein Warnton: Die Lücke ist eine Tatsache mit Datum.
        <div className="mb-4 flex max-w-[76ch] gap-2.5 rounded-xl border border-dashed border-muted-foreground/45 px-3.5 py-3">
          <CircleDashed className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0">
            <p className="text-[15px] font-medium leading-snug text-foreground">{plan.report_note}</p>
          </div>
        </div>
      )}
      {plan.news && <News news={plan.news} />}
      {stations.length > 0 && (
        <>
          <ol className="flex flex-col">
            {visible.map((entry, i) => (
              <LogSection key={`${entry.kind}-${entry.year}`} entry={entry} stations={stations} currentIndex={stations.length - 1}
                // Steht über der jüngsten Station eine Lücke, ist sie nicht „aktuell“, sondern das Letzte, was zu finden war.
                currentLabel={log[0]?.kind === "gap" ? "Zuletzt im Rat" : "Aktueller Stand"} highlighted={highlighted} row={i} />
            ))}
          </ol>
          {hidden.length > 0 && (
            <button type="button" onClick={() => setShowAll(true)}
              className="inline-flex min-h-11 items-center gap-1.5 text-left text-meta font-medium text-primary hover:underline">
              <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                Frühere Jahre zeigen ({hidden[hidden.length - 1].year}–{hidden[0].year_to}
                {hiddenStations > 0 && `, ${hiddenStations} ${hiddenStations === 1 ? "Station" : "Stationen"}`})
              </span>
            </button>
          )}
        </>
      )}
    </section>
  );
}
