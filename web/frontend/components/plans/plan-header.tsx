"use client";

// Die Kopfbühne der Planseite: Name und Beschluss, darunter LAUFZEIT — das
// Zeitband des Plans auf seiner eigenen Achse — und die Eckdaten als Kacheln.
// Eine getönte Fläche über die ganze Breite, dieselbe wie im Kopf der
// Übersicht: Hier steht, WAS der Plan ist und WANN er gilt; alles Weitere
// (Berichte, Maßnahmen, Beschlüsse) hängt darunter.
//
// Das Band beantwortet auf einen Blick, was vorher eine Tabelle aus „Beginn“,
// „Ende“ und „Nächste Überprüfung“ war — und zusätzlich, wann berichtet wurde.
// Jede Marke ist ein Knopf zum Eintrag im Zeitstrahl darunter.
//
// Kein Fortschrittsbalken (Plan § 3.4): Das Band zeigt Laufzeit. „Seit dem
// Beschluss“ und „Laufzeit noch“ stehen als Zeitspannen da, nie als Anteil.

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";
import { arrivingByBand } from "@/components/plans/band-transition";
import { voteLabel } from "@/components/decision-ui";
import { AdoptionBadge, Kicker, StatusBadge } from "@/components/plans/parts";
import { AxisGrid, BandShape, Diamond, MarkGlyph, TimeAxis } from "@/components/plans/time-band";
import { decisionHref, planHref } from "@/lib/routes";
import { formatDate, percent, stationKind, type PlanDetail, type PlanRunway, type PlanStation } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** Ein Termin, den der Plan selbst nennt: ein Wimpel über dem Band. Neutral wie alles hier —
 *  ob er vor oder hinter „heute“ liegt, ändert an ihm nichts (Plan § 3.4: kein „zu spät“). */
function DueGlyph({ className }: { className?: string }) {
  return (
    <span className={cn("relative block h-[19px] w-[10px]", className)}>
      <span className="absolute bottom-0 left-0 h-full w-[1.5px] rounded-full bg-primary" />
      <span className="absolute left-[1.5px] top-0 h-[8px] w-[8px] bg-primary/80 [clip-path:polygon(0_0,100%_50%,0_100%)]" />
    </span>
  );
}

function Runway({ runway, stations, onStation, onPoint }: {
  runway: PlanRunway; stations: readonly PlanStation[]; onStation: (index: number) => void;
  onPoint: (index: number) => void;
}) {
  // Kam die Seite über das Band der Übersicht herein, ist das Band schon „angekommen“: Es wächst
  // dann nicht noch einmal, und die Marken stehen sofort (components/plans/band-transition.ts).
  const [build] = useState(() => !arrivingByBand());
  const pop = (delay: number) => (build ? { className: "animate-pop-in", style: { animationDelay: `${delay}ms` } } : {});
  return (
    <div className="@container/axis">
      <div className="relative h-[68px]">
        {runway.archive_from != null && (
          // Vor 2018 kennt das Ratsinformationssystem keine Sitzungen: Die Fläche
          // sagt „hier fehlen die Daten“, nicht „hier war nichts“.
          <span aria-hidden className="absolute inset-y-0 left-0 border-r border-dashed border-muted-foreground/50 bg-muted-foreground/[0.07]"
            style={{ width: percent(runway.archive_from) }}>
            <span className="absolute bottom-1 left-1.5 font-mono text-[10px] leading-none text-muted-foreground">vor 2018</span>
          </span>
        )}
        <div aria-hidden className="absolute inset-0"><AxisGrid ticks={runway.ticks} today={runway.today} /></div>
        {runway.band && <BandShape band={runway.band} look={runway.style} fade={1 - runway.band.x1} large growing={build} arriving />}
        {runway.review && (
          <span title={`Überprüfung oder Fortschreibung vorgesehen: ${runway.review.label}`}
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: percent(runway.review.x) }}>
            <Diamond large />
          </span>
        )}
        {runway.marks.map((mark, i) => {
          const station = stations[mark.station];
          const what = `${stationKind(mark)} vom ${formatDate(mark.date)}`;
          return (
            <button key={mark.station} type="button" onClick={() => onStation(mark.station)}
              title={station ? `${what} · ${station.title}${station.summary ? ` — laut Bericht: ${station.summary.text}` : ""}` : what}
              aria-label={`${what}${station ? `: ${station.title}` : ""} – im Zeitstrahl zeigen`}
              className="group/mark absolute top-1/2 flex h-11 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              style={{ left: percent(mark.x), zIndex: mark.kind === "preparation" ? 1 : mark.kind === "report" || mark.kind === "evaluation" ? 3 : 2 }}>
              {/* Chronologisch aufgehen, wie der Zeitstrahl darunter; ab der 16. Marke gemeinsam. */}
              <span {...pop(260 + Math.min(i, 15) * 35)}>
                <MarkGlyph kind={mark.kind} oral={mark.oral} look={runway.style} large
                  className="transition-transform duration-tipp ease-out-strong group-hover/mark:scale-125 group-focus-visible/mark:scale-125" />
              </span>
            </button>
          );
        })}
        {runway.dues.map((due, i) => (
          // Der Fuß des Wimpels steht auf der Mitte des Bandes, an seinem Tag; der Knopf darum ist die Tippfläche.
          <button key={`${due.point}-${due.date}`} type="button" onClick={() => onPoint(due.point)}
            title={`Laut Plan ${due.label}: ${due.text}`}
            aria-label={`Termin laut Plan, ${due.label}: ${due.text} – im Inhalt zeigen`}
            className="group/due absolute top-1/2 h-11 w-5 -translate-x-1/2 -translate-y-1/2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            style={{ left: percent(due.x), zIndex: 4 }}>
            <span {...pop(260 + Math.min(runway.marks.length, 15) * 35 + i * 60)}
              className={cn("absolute bottom-1/2 left-1/2 -ml-[0.75px]", build && "animate-pop-in")}>
              <DueGlyph className="origin-bottom-left transition-transform duration-tipp ease-out-strong group-hover/due:scale-125 group-focus-visible/due:scale-125" />
            </span>
          </button>
        ))}
      </div>
      <TimeAxis ticks={runway.ticks} today={runway.today} className="h-8 border-t border-border/70" below />
    </div>
  );
}

/** Nur die Zeichen, die auf DIESEM Band vorkommen. */
function RunwayLegend({ runway }: { runway: PlanRunway }) {
  const kinds = new Set(runway.marks.map((m) => (m.kind === "report" || m.kind === "evaluation") ? (m.oral ? "oral" : "report") : m.kind));
  const item = "inline-flex items-center gap-1.5 whitespace-nowrap";
  return (
    <ul aria-label="Legende" className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-muted-foreground">
      {(kinds.has("adoption") || kinds.has("amendment")) && (
        <li className={item}><MarkGlyph kind="adoption" oral={false} look={runway.style} className="h-3" /> Beschluss</li>
      )}
      {kinds.has("report") && <li className={item}><MarkGlyph kind="report" oral={false} look={runway.style} /> Bericht</li>}
      {kinds.has("oral") && <li className={item}><MarkGlyph kind="report" oral look={runway.style} /> mündlich, ohne Text</li>}
      {kinds.has("preparation") && (
        <li className={item}><MarkGlyph kind="preparation" oral={false} look={runway.style} /> vor dem Beschluss</li>
      )}
      {runway.review && <li className={item}><Diamond /> Überprüfung vorgesehen</li>}
      {runway.dues.length > 0 && <li className={item}><DueGlyph className="scale-[0.7]" /> Termin laut Plan</li>}
      {runway.band?.open_end && <li className={item}>Band läuft aus: ohne Enddatum</li>}
      {runway.archive_from != null && <li className={item}>vor 2018: nicht im Ratsinformationssystem</li>}
    </ul>
  );
}

type Fact = { label: string; value: string; detail?: React.ReactNode };

/** Spalten je Anzahl, damit keine Zeile ein Loch lässt: schmal zwei, ab
 *  mittlerer Breite drei oder vier, breit alle nebeneinander. Bei fünf Kacheln
 *  nimmt die erste (eine Zeitspanne, der längste Wert) in der mittleren Breite
 *  zwei von drei Spalten. Breit bleibt eine Kachel höchstens ein Viertel der
 *  Bühne: Zwei Kacheln über 1.100 px wären zwei leere Flächen mit je einer Zahl —
 *  sie stehen linksbündig wie der Titel darüber. */
const FACT_COLUMNS: Record<number, string> = {
  1: "@xl:grid-cols-2 @4xl:grid-cols-4", 2: "@xl:grid-cols-2 @4xl:grid-cols-4", 3: "@xl:grid-cols-3 @4xl:grid-cols-4",
  4: "@xl:grid-cols-4", 5: "@xl:grid-cols-3 @4xl:grid-cols-5", 6: "@xl:grid-cols-3 @4xl:grid-cols-6",
};

function Facts({ facts }: { facts: (Fact | false | null | undefined | "")[] }) {
  const shown = facts.filter((f): f is Fact => !!f);
  return (
    <dl className={cn("mt-4 grid grid-cols-2 gap-2", FACT_COLUMNS[shown.length])}>
      {shown.map((fact, i) => (
        <div key={fact.label} className={cn("min-w-0 rounded-[10px] border border-border/70 bg-card px-3 py-2.5",
          i === 0 && shown.length % 2 === 1 && (shown.length === 5 ? "col-span-2 @4xl:col-span-1" : "col-span-2 @xl:col-span-1"))}>
          <dt className="font-mono text-[10px] uppercase leading-snug tracking-[0.08em] text-muted-foreground">{fact.label}</dt>
          <dd className="mt-1">
            <span className="block break-words font-display text-[19px] font-bold leading-tight tabular-nums text-foreground">{fact.value}</span>
            {fact.detail && <span className="mt-0.5 block text-meta text-muted-foreground">{fact.detail}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function TemplateRef({ number, url }: { number: string; url: string | null }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2">
      <span className="font-mono text-meta">{number}</span>
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 text-meta text-muted-foreground hover:text-primary">
          Ratsinfo <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      )}
    </span>
  );
}

function Title({ plan }: { plan: PlanDetail }) {
  const adoption = plan.adoption;
  const vote = adoption ? voteLabel(adoption.vote) : "";
  return (
    <header>
      <Kicker>{[plan.field_label, plan.kind_label, plan.owner].filter(Boolean).join(" · ")}</Kicker>
      <h1 className="mt-1.5 max-w-[28ch] hyphens-auto break-words font-display text-[26px] font-bold leading-tight text-foreground sm:text-[34px] sm:leading-[1.15]">
        {plan.title}
      </h1>
      {plan.office && <p className="mt-1.5 text-hinweis text-muted-foreground">{plan.office}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <AdoptionBadge mode={adoption ? adoption.mode : null} />
        {adoption && (
          <span className="text-meta text-muted-foreground">
            {[adoption.committee, formatDate(adoption.date), vote, adoption.label].filter(Boolean).join(" · ")}
            {!adoption.template_number && " · vor 2018, nicht im Ratsinformationssystem"}
          </span>
        )}
        {adoption?.template_number && (
          <span className="inline-flex flex-wrap items-center gap-x-2">
            {adoption.decision_id != null ? (
              <Link href={decisionHref(adoption.decision_id)} className="font-mono text-meta text-primary hover:underline">{adoption.template_number}</Link>
            ) : <span className="font-mono text-meta">{adoption.template_number}</span>}
            {adoption.url && (
              <a href={adoption.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-meta text-muted-foreground hover:text-primary">
                Ratsinfo <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
          </span>
        )}
        <StatusBadge plan={plan} short />
        {plan.website && (
          <a href={plan.website} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-meta text-primary hover:underline">
            Seite der Stadt <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        )}
      </div>
    </header>
  );
}

export function PlanHeader({ plan, onStation, onPoint }: {
  plan: PlanDetail; onStation: (index: number) => void;
  /** Ein Tipp auf einen Termin im Band führt zum Kernpunkt, der ihn nennt. */
  onPoint: (index: number) => void;
}) {
  const begin = plan.start_label ?? (plan.adoption ? formatDate(plan.adoption.date) : null);
  // „Seit … · ohne Enddatum“ gilt nur, solange der Plan läuft: Ein abgelöster
  // Plan ohne Enddatum hat eines bekommen — er beginnt nur noch („ab 2015“).
  const running = plan.status === "running";
  const span = plan.end_label ? `${begin} – ${plan.end_label}` : running ? `seit ${begin}` : `ab ${begin}`;
  const spanLabel = plan.adoption
    ? `${span}${running && !plan.end_label ? " · ohne Enddatum" : ""}`
    : (plan.since ? "noch nicht beschlossen" : "noch offen");
  const latest = plan.latest_report;
  return (
    <section aria-label="Der Plan und seine Laufzeit"
      className="@container rounded-[18px] border border-primary/15 bg-primary/[0.04] p-4 sm:p-6">
      <Title plan={plan} />
      <div className="mb-3 mt-6 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]">Laufzeit</Kicker>
        <p className="font-mono text-meta text-muted-foreground">{spanLabel}</p>
      </div>
      {plan.runway && (
        <>
          <Runway runway={plan.runway} stations={plan.timeline.stations} onStation={onStation} onPoint={onPoint} />
          <div className="mt-2"><RunwayLegend runway={plan.runway} /></div>
        </>
      )}
      {(plan.predecessor || plan.successor) && (
        // Die Kette in Leserichtung der Zeit: links, was davor galt, rechts, was folgt.
        <div className="mt-4 flex flex-wrap items-stretch justify-between gap-2">
          {plan.predecessor ? (
            <Link href={planHref(plan.predecessor.key)} className="group flex w-full min-w-0 items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 hover:border-primary/40 @xl:w-auto @xl:max-w-[48%]">
              <ArrowLeft className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-fluss ease-out-strong group-hover:-translate-x-0.5" aria-hidden />
              <span className="min-w-0">
                <span className="block font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">Vorgänger</span>
                <span className="block break-words text-[14px] font-medium leading-snug text-foreground">{plan.predecessor.title}</span>
              </span>
            </Link>
          ) : <span className="hidden @xl:block" />}
          {plan.successor && (
            <Link href={planHref(plan.successor.key)} className="group ml-auto flex w-full min-w-0 items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 hover:border-primary/40 @xl:w-auto @xl:max-w-[48%] @xl:text-right">
              <span className="min-w-0 flex-1">
                <span className="block font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                  Nachfolger{!plan.successor.adopted && " · noch nicht beschlossen"}
                </span>
                <span className="block break-words text-[14px] font-medium leading-snug text-foreground">{plan.successor.title}</span>
              </span>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-fluss ease-out-strong group-hover:translate-x-0.5" aria-hidden />
            </Link>
          )}
        </div>
      )}
      <Facts facts={[
        plan.since && { label: plan.since.label, value: plan.since.value },
        plan.remaining && { label: plan.remaining.label, value: plan.remaining.value, detail: `bis ${plan.end_label}` },
        !plan.since && begin && {
          label: "Laufzeit", value: span, detail: plan.horizon_note ?? (plan.group === "ended" ? plan.status_label : undefined),
        },
        plan.review_label && { label: "Nächste Überprüfung", value: plan.review_label },
        {
          // Die Null steht als Strich: „keinen gefunden“ ist eine Aussage über den Bestand, keine Messung.
          label: "Berichte im Rat", value: plan.report_count > 0 ? `${plan.report_count}` : "–",
          // Der Berichtsstand (§ 3.3a) steht dabei: eine Aussage über die Berichte, nicht über die Arbeit.
          detail: plan.report_count === 0 ? <>
            <span className="block">keinen gefunden</span>
            {plan.report_state.state === "not_yet_due" && (
              <span className="block">{plan.report_state.label}{plan.report_state.hint ? ` · ${plan.report_state.hint}` : ""}</span>
            )}
          </> : <>
            <span className="block font-medium text-foreground">{plan.report_state.label}</span>
            {latest && <span className="block">zuletzt {formatDate(latest.date)}</span>}
            {plan.oral_report_count > 0 && <span className="block">davon {plan.oral_report_count} mündlich, ohne Text</span>}
          </>,
        },
        plan.measures && {
          label: "Maßnahmen", value: `${plan.measures.count}`,
          detail: plan.measures.source.as_of_label ? `Liste vom ${plan.measures.source.as_of_label}` : undefined,
        },
      ]} />
      {(plan.horizon_note && plan.since) && <p className="mt-3 max-w-[76ch] text-hinweis text-muted-foreground">Laufzeit laut Plan: {plan.horizon_note}.</p>}
      {(plan.commissioned || plan.concluded) && (
        <dl className="mt-3 max-w-[76ch] space-y-2 text-[14px] leading-relaxed">
          {plan.commissioned && (
            <div>
              <dt className="text-meta text-muted-foreground">Arbeit begonnen{plan.commissioned.date ? ` · ${formatDate(plan.commissioned.date)}` : ""}</dt>
              <dd className="break-words text-foreground">
                {plan.commissioned.title ?? plan.commissioned.template_number}{" "}
                <TemplateRef number={plan.commissioned.template_number} url={plan.commissioned.url} />
              </dd>
            </div>
          )}
          {plan.concluded && (
            <div>
              <dt className="text-meta text-muted-foreground">Ausgewertet in</dt>
              <dd className="break-words text-foreground">
                {plan.concluded.title ?? plan.concluded.template_number}{" "}
                <TemplateRef number={plan.concluded.template_number} url={plan.concluded.url} />
              </dd>
            </div>
          )}
        </dl>
      )}
      {plan.note && <p className="mt-3 max-w-[76ch] text-hinweis text-muted-foreground">{plan.note}</p>}
    </section>
  );
}
