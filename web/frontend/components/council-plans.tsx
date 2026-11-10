"use client";

// <PlansView> — „Pläne der Stadt“ in der Analyse (Schalter `plaene`,
// docs/plan-ziele-plaene.md § 3.1). Ersetzt hinter dem Schalter die Ziel-Seite.
//
// DIE ERZÄHLUNG: Ein Plan ist eine Strecke in der Zeit. Jede Zeile trägt
// deshalb ihr Zeitband auf EINER gemeinsamen Achse — vom Beginn des Bestands
// (2018) bis zehn Jahre nach vorn, der Strich für heute läuft quer durch alle.
// Man sieht ohne ein Wort der Wertung, wie lange ein Plan gilt, wie oft im
// Rat berichtet wurde und wo es still geworden ist: Die Lücke ist ein leeres
// Stück Band, kein Warnzeichen.
//
// Gebaut wird alles im Backend (council/plan_pages.py): Gruppen, Sortierung,
// Kicker, Lagen auf der Achse, „letzter Bericht“ und der Satz, wenn der
// Bestand schweigt. Hier wird nur gezeichnet.
//
// Was die Seite NICHT zeigt, steht in § 3.4: keine Note, keine Quote über
// Pläne, kein Fortschrittsbalken, kein Rot.
//
// ZWEI WEGE DURCH DIE LISTE. Nach Status gegliedert (die Vorgabe) — oder als
// eine Liste in einer von drei Reihenfolgen: zuletzt berichtet, endet bald,
// lange kein Bericht. Welche Pläne in welcher Folge, rechnet das Backend
// (`views`); beim Wechsel gleiten die Zeilen an ihren neuen Platz (lib/flip.ts).
// Ein Tipp auf eine Zeile klappt auf, worum es im Plan geht — Zweck, zwei
// Kernpunkte, der letzte Bericht —, der Titel führt zum Plan.

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, ChevronRight, CircleDashed, Info, MessageCircleQuestion } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { ChartSkeleton, EmptyState, ScrollZeile } from "@/components/ui";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Kicker, StatusBadge } from "@/components/plans/parts";
import { AxisGrid, Diamond, MarkGlyph, TimeAxis, TimeBand } from "@/components/plans/time-band";
import { STAFFEL, staffelStil } from "@/components/staffel";
import { useFetch } from "@/lib/use-fetch";
import { bandTransition } from "@/components/plans/band-transition";
import { useFlip } from "@/lib/flip";
import { decisionHref, fragenHref, planHref } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { byField, formatDate, reportCount, type PlanAxis, type PlanCard, type PlanGroup, type PlanOverview, type PlanView, statusSummary } from "@/lib/plans";

/** Text · Zeitband · Berichtslage. Schmal untereinander, ab Tablet-Breite
 *  steht das Band neben dem Text, breit bekommt die Berichtslage ihre Spalte.
 *  Kopfzeile, Feld-Zeilen und Plan-Zeilen teilen sich diese Spalten — nur so
 *  liegen die Jahreslinien von Zeile zu Zeile übereinander. */
const COLUMNS = "grid grid-cols-1 @2xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] @5xl:grid-cols-[minmax(0,23rem)_minmax(0,1fr)_17.5rem]";
const LANE_CELL = "px-4 @2xl:col-start-2 @2xl:row-start-1 @2xl:px-3";

/** Der Weg von der Zeile zur Planseite: Das Band der Zeile wird zum Band im Kopf des Plans
 *  (components/plans/band-transition.ts). Wo der Browser das nicht kann, ist es ein gewöhnlicher Link. */
function openPlan(e: React.MouseEvent, band: HTMLElement | null) {
  bandTransition(e, band);
}

function HowCounted() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex items-center gap-1 whitespace-nowrap align-baseline font-medium text-primary hover:underline">
          <Info className="h-3.5 w-3.5" aria-hidden /> Wie wird gezählt?
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-3 text-xs leading-relaxed text-muted-foreground">
        Welche Pläne hier stehen, legt ein von Hand gepflegtes Register fest: Pläne mit Maßnahmen und
        Ratsbeschluss, Rahmenpläne und Strategien, Pflicht- und Fachpläne. Die Berichte findet Ratslotse
        über die Titel der Tagesordnungspunkte im Ratsinformationssystem. Nichtöffentliche Sitzungen,
        Mitteilungen ohne Vorlage und Berichte außerhalb des Ratsinformationssystems sieht Ratslotse nicht —
        „kein Bericht“ heißt deshalb „keinen gefunden“.
      </PopoverContent>
    </Popover>
  );
}

type HeadRow = { key: string; planKey: string; when: string; plan: string; what: string };

/** Zwei kurze Listen im Kopf: was zuletzt im Rat war und was die Pläne selbst
 *  als Nächstes vorsehen. Jede Zeile führt zum Plan. */
function HeadList({ kicker, rows }: { kicker: string; rows: HeadRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card">
      <Kicker className="px-3.5 pt-3">{kicker}</Kicker>
      <ul className="mt-1 divide-y divide-border/70">
        {rows.map((row, i) => (
          // Schmal nur die ersten zwei: Auf dem Handy ist der Kopf sonst länger als ein Bildschirm.
          <li key={row.key} className={cn(i >= 2 && "hidden @3xl/head:block")}>
            <Link href={planHref(row.planKey)} prefetch={false}
              className="flex gap-3 px-3.5 py-2 hover:bg-primary/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
              <span className="w-[5.25rem] shrink-0 pt-px font-mono text-meta text-muted-foreground">{row.when}</span>
              <span className="min-w-0 flex-1">
                <span className="block break-words text-[14px] font-medium leading-snug text-foreground">{row.plan}</span>
                <span className="block break-words text-meta text-muted-foreground">{row.what}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

const COUNTER_LABELS: Record<PlanGroup["key"], string> = {
  running: "laufen",
  preparing: "in Arbeit",
  ended: "abgelaufen oder abgelöst",
};

function Stage({ data }: { data: PlanOverview }) {
  return (
    <section aria-labelledby="plans-title" className="@container/head rounded-[18px] border border-primary/15 bg-primary/[0.04] p-4 sm:p-6">
      <Kicker>Pläne der Stadt · Stand {data.as_of_label}</Kicker>
      <div className="mt-2 grid gap-x-10 gap-y-4 @4xl/head:grid-cols-[minmax(0,1fr)_auto] @4xl/head:items-end">
        <div className="min-w-0">
          <h2 id="plans-title" className="font-display text-[22px] font-bold leading-tight text-foreground sm:text-[28px]">
            Was sich Oldenburg vorgenommen hat
          </h2>
          <p className="mt-1.5 max-w-[60ch] text-hinweis text-muted-foreground">
            Zu jedem Plan: wann er beschlossen wurde, wie lange er läuft und was die Verwaltung dem
            Rat seither berichtet hat. <HowCounted />
          </p>
        </div>
        <ul className="flex flex-wrap gap-x-7 gap-y-2">
          {data.groups.filter((g) => g.plans.length > 0).map((g) => (
            <li key={g.key}>
              <a href={`#plans-${g.key}`} className="group block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <span className="block font-display text-[30px] font-bold tabular-nums leading-none text-foreground">{g.plans.length}</span>
                <span className="mt-1 block text-meta text-muted-foreground group-hover:text-primary">{COUNTER_LABELS[g.key]}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-5 grid gap-3 @3xl/head:grid-cols-2">
        <HeadList kicker="Zuletzt im Rat berichtet" rows={data.recent.map((r) => ({
          key: `${r.plan_key}-${r.date}-${r.template_number ?? r.title}`, planKey: r.plan_key,
          when: formatDate(r.date), plan: r.plan_title,
          what: r.oral ? `${r.title} · mündlich, ohne Text` : r.title,
        }))} />
        <HeadList kicker="Als Nächstes laut Plan" rows={data.upcoming.map((u) => ({
          key: `${u.plan_key}-${u.kind}`, planKey: u.plan_key, when: u.date_label, plan: u.plan_title, what: u.text,
        }))} />
      </div>
    </section>
  );
}

function FieldChips({ data, field, setField }: {
  data: PlanOverview; field: string | null; setField: (f: string | null) => void;
}) {
  const chip = "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs font-medium transition-[color,background-color,transform] duration-tipp ease-out-strong active:scale-[0.96]";
  const on = "bg-primary text-primary-foreground";
  const off = "border border-input bg-card text-foreground hover:bg-accent";
  return (
    <ScrollZeile role="group" aria-label="Nach Themenfeld filtern" className="-mx-1 flex gap-1.5 px-1 py-1 sm:flex-wrap">
      <button type="button" aria-pressed={field === null} onClick={() => setField(null)} className={cn(chip, field === null ? on : off)}>
        Alle <span className="font-mono text-[10.5px] opacity-80">{data.count}</span>
      </button>
      {data.fields.map((f) => (
        <button key={f.key} type="button" aria-pressed={field === f.key}
          onClick={() => setField(field === f.key ? null : f.key)} className={cn(chip, field === f.key ? on : off)}>
          {f.label} <span className="font-mono text-[10.5px] opacity-80">{f.count}</span>
        </button>
      ))}
    </ScrollZeile>
  );
}

type ViewKey = "status" | PlanView["key"];

/** Gliederung oder Reihenfolge: „Nach Status“ ist die Vorgabe, die anderen drei legen alle Pläne
 *  in EINE Liste. Leere Ansichten (unter dem gewählten Themenfeld) bleiben wählbar und sagen es dann. */
function ViewChips({ views, view, setView }: {
  views: readonly PlanView[]; view: ViewKey; setView: (v: ViewKey) => void;
}) {
  const chip = "inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-full px-3 text-xs font-medium transition-[color,background-color,transform] duration-tipp ease-out-strong active:scale-[0.96]";
  const on = "bg-foreground text-background";
  const off = "border border-input bg-card text-foreground hover:bg-accent";
  const options: { key: ViewKey; label: string }[] = [{ key: "status", label: "Nach Status" }, ...views.map((v) => ({ key: v.key, label: v.label }))];
  return (
    <ScrollZeile role="group" aria-label="Reihenfolge der Pläne" className="-mx-1 flex items-center gap-1.5 px-1 py-1 sm:flex-wrap">
      <span className="shrink-0 pr-0.5 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">Ansicht</span>
      {options.map((o) => (
        <button key={o.key} type="button" aria-pressed={view === o.key} onClick={() => setView(o.key)}
          className={cn(chip, view === o.key ? on : off)}>
          {o.label}
        </button>
      ))}
    </ScrollZeile>
  );
}

/** Die Zeichen des Zeitbands, einmal erklärt — mit denselben Formen wie im Band. */
function Legend() {
  const item = "inline-flex items-center gap-1.5 whitespace-nowrap";
  const band = "inline-block h-2.5 w-5 rounded-full";
  return (
    <ul aria-label="Legende der Zeitbänder" className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-muted-foreground">
      <li className={item}><span className={cn(band, "border border-primary/45 bg-primary/20")} aria-hidden /> beschlossen</li>
      <li className={item}><span className={cn(band, "border border-muted-foreground/45 bg-muted-foreground/15")} aria-hidden /> zur Kenntnis genommen</li>
      <li className={item}><span className={cn(band, "border-[1.5px] border-dashed border-primary/60")} aria-hidden /> in Arbeit</li>
      <li className={item}>
        <span className={cn(band, "rounded-r-none border border-r-0 border-primary/45 bg-primary/20 [mask-image:linear-gradient(to_right,black,transparent)]")} aria-hidden />
        ohne Enddatum
      </li>
      <li className={item}><MarkGlyph kind="report" oral={false} look="adopted" /> Bericht</li>
      <li className={item}><MarkGlyph kind="report" oral look="adopted" /> mündlich, ohne Text</li>
      <li className={item}><MarkGlyph kind="adoption" oral={false} look="adopted" className="h-3" /> Beschluss</li>
      <li className={item}><Diamond /> Überprüfung vorgesehen</li>
      <li className={item}><span className="inline-block h-px w-5 bg-muted-foreground/60" aria-hidden /> Vorgänger</li>
    </ul>
  );
}

function ReportState({ plan }: { plan: PlanCard }) {
  const latest = plan.latest_report;
  return (
    <div className="min-w-0 space-y-1 text-meta">
      {plan.status === "superseded" && plan.successor ? (
        // Kein Abzeichen: Der Name des Nachfolgers ist ein Satz, keine Pille.
        <p className="text-muted-foreground">abgelöst durch <span className="font-medium text-foreground">{plan.successor.title}</span></p>
      ) : plan.group !== "running" && <StatusBadge plan={plan} />}
      {plan.report_count > 0 && (
        <p className="text-foreground">
          <span className="font-medium">{reportCount(plan.report_count)}</span>
          {/* Der Lücken-Satz nennt das Datum schon („Seit 02/2024 …“). */}
          {latest && !plan.report_note && <span className="text-muted-foreground"> · zuletzt {formatDate(latest.date)}</span>}
        </p>
      )}
      {plan.report_note && (
        <p className="flex gap-1.5 text-muted-foreground">
          <CircleDashed className="mt-[3px] h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0">{plan.report_note}</span>
        </p>
      )}
      {plan.report_state.state === "not_yet_due" && (
        <p className="text-muted-foreground">
          {plan.report_state.label}{plan.report_state.hint ? ` · ${plan.report_state.hint}` : ""}
        </p>
      )}
      {plan.status_brief && (
        // In den Worten der Stadt, mit Herkunft und Stichtag — keine Quote, kein Balken (§ 3.1).
        <p className="text-foreground">
          {statusSummary(plan.status_brief)}
          <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
            {plan.status_brief.origin_label} · Stand {plan.status_brief.as_of_label}
          </span>
        </p>
      )}
    </div>
  );
}

/** Was eine aufgeklappte Zeile zeigt: worum es im Plan geht und was zuletzt berichtet wurde.
 *  Ohne Zitat — die Belege stehen auf der Planseite, einen Tipp weiter. */
function RowBrief({ plan, onOpen }: { plan: PlanCard; onOpen: (e: React.MouseEvent) => void }) {
  const { brief, latest_report: latest } = plan;
  return (
    <div className="relative z-[1] px-4 pb-4 pt-0.5">
      <div className="rounded-xl border border-primary/15 bg-primary/[0.04] p-3.5">
        <div className="max-w-[76ch]">
          {brief && (
            <>
              <Kicker>{brief.heading}</Kicker>
              <p className="mt-1 break-words text-[15px] font-medium leading-snug text-foreground">{brief.purpose}</p>
              <ul className="mt-2 space-y-1.5">
                {brief.points.map((point) => (
                  <li key={point} className="flex gap-2 text-[14px] leading-snug text-foreground">
                    <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
                    <span className="min-w-0 break-words">{point}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {latest && (
            <div className={cn(brief && "mt-3")}>
              <Kicker>Letzter Bericht · {formatDate(latest.date)}{latest.committee ? ` · ${latest.committee}` : ""}</Kicker>
              <p className="mt-0.5 break-words text-[14px] leading-snug text-foreground">
                {latest.decision_id != null ? (
                  <Link href={decisionHref(latest.decision_id)} prefetch={false} className="hover:text-primary hover:underline">{latest.title}</Link>
                ) : latest.title}
                {latest.oral && <span className="text-muted-foreground"> · mündlich, ohne Text</span>}
              </p>
            </div>
          )}
        </div>
        <Link href={planHref(plan.key)} prefetch={false} onClick={onOpen}
          className="mt-3 inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium text-primary hover:underline">
          {brief && brief.count > brief.points.length ? `Zum Plan · alle ${brief.count} Kernpunkte mit Beleg` : "Zum Plan"}
          <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
        </Link>
      </div>
    </div>
  );
}

function PlanRow({ plan, axis, showField, index, stagger, extra }: {
  plan: PlanCard; axis: PlanAxis; showField: boolean; index: number;
  /** Ein Zusatz im Kicker, den nur diese Ansicht braucht („noch 4 Jahre, 1 Monat“). */
  extra?: string | null;
  /** Nur beim ersten Auftritt der Liste läuft die Zeile gestaffelt ein — danach gleitet sie (FLIP). */
  stagger: boolean;
}) {
  const [open, setOpen] = useState(false);
  // Aufklappen lohnt, wo es etwas zu zeigen gibt; sonst führt die ganze Zeile zum Plan, wie bisher.
  const expandable = !!plan.brief || !!plan.latest_report;
  const goto = (e: React.MouseEvent) => openPlan(e, e.currentTarget.closest("li")?.querySelector<HTMLElement>("[data-band-shape]") ?? null);
  const Chevron = expandable ? ChevronDown : ChevronRight;
  const chevron = cn("mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform ease-out-strong",
    expandable ? cn("duration-weg", open && "rotate-180") : "duration-fluss group-hover:translate-x-0.5");
  return (
    <li data-flip={plan.key} className={cn(stagger && STAFFEL, "group relative border-t border-border/70", open ? "bg-primary/[0.02]" : "hover:bg-primary/[0.04]")}
      style={stagger ? staffelStil(index) : undefined}>
      <div className={COLUMNS}>
        <div className="min-w-0 px-4 pb-1.5 pt-3 @2xl:col-start-1 @2xl:row-start-1 @5xl:pb-3">
          <h4 className="flex items-start gap-2">
            <Link href={planHref(plan.key)} prefetch={false} onClick={goto}
              className={cn("min-w-0 flex-1 break-words text-quelle font-semibold leading-snug text-foreground hover:text-primary focus-visible:outline-none",
                expandable ? "relative z-[1] rounded-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                  : "after:absolute after:inset-0 after:content-[''] group-hover:text-primary focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring")}>
              {plan.title}
            </Link>
            <Chevron className={cn(chevron, "@5xl:hidden")} aria-hidden />
          </h4>
          <Kicker className="mt-1">
            {[showField ? plan.kicker : plan.timing, extra, plan.measure_count ? `${plan.measure_count} Maßnahmen` : null].filter(Boolean).join(" · ")}
          </Kicker>
        </div>
        <div className={cn(LANE_CELL, "@2xl:row-span-2 @5xl:row-span-1")}>
          <TimeBand lane={plan.lane} ticks={axis.ticks} today={axis.today} fade={axis.fade} className="h-7 @2xl:h-full @2xl:min-h-11" />
        </div>
        <div className="flex min-w-0 items-start gap-2 px-4 pb-3 pt-1.5 @2xl:col-start-1 @2xl:row-start-2 @2xl:pt-0 @5xl:col-start-3 @5xl:row-start-1 @5xl:pt-3">
          <div className="min-w-0 flex-1"><ReportState plan={plan} /></div>
          <Chevron className={cn(chevron, "hidden @5xl:block")} aria-hidden />
        </div>
      </div>
      {expandable && (
        <>
          {/* Die Tippfläche der Zeile: liegt über dem Kopf der Zeile, unter Titel-Link und Aufklapp-Inhalt. */}
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
            aria-label={`${plan.title}: ${open ? "Kurzfassung schließen" : "Kurzfassung zeigen"}`}
            className="absolute inset-0 h-full w-full cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" />
          <Aufklapp offen={open}><RowBrief plan={plan} onOpen={goto} /></Aufklapp>
        </>
      )}
    </li>
  );
}

function GroupCard({ group, axis, splitByField, showField, stagger, hint, remaining = false }: {
  group: { key: string; label: string; plans: PlanCard[] }; axis: PlanAxis;
  /** Die lange Gruppe bekommt Zwischenzeilen je Themenfeld. */
  splitByField: boolean;
  /** Steht das Themenfeld im Kicker jeder Zeile? Nicht, wenn es schon darüber steht oder gefiltert ist. */
  showField: boolean;
  stagger: boolean;
  /** Ein Satz unter dem Kopf: was diese Ansicht zeigt. */
  hint?: string;
  /** „Endet bald“: Jede Zeile sagt, wie lange der Plan noch läuft. */
  remaining?: boolean;
}) {
  const fields = splitByField ? byField(group.plans) : [{ key: "all", label: "", plans: group.plans }];
  let index = 0;
  return (
    <section id={`plans-${group.key}`} aria-labelledby={`plans-${group.key}-title`}
      className="@container scroll-mt-20 overflow-clip rounded-2xl border border-border bg-card shadow-sm">
      {/* Die Achse bleibt beim Scrollen stehen: 31 Zeilen ohne Jahreszahlen wären nur noch Striche. */}
      <div className={cn(COLUMNS, "sticky top-[calc(env(safe-area-inset-top)+3.8125rem)] z-10 bg-card/95 backdrop-blur desk:top-0")}>
        <div className="flex items-baseline gap-2.5 px-4 pb-1 pt-3.5 @2xl:pb-3">
          <h3 id={`plans-${group.key}-title`} className="font-display text-[17px] font-bold leading-tight text-foreground">{group.label}</h3>
          <span className="font-mono text-meta text-muted-foreground">{group.plans.length}</span>
        </div>
        <div className={cn(LANE_CELL, "@container/axis")}>
          <TimeAxis ticks={axis.ticks} today={axis.today} />
        </div>
      </div>
      {hint && (
        <div className="border-t border-border/70 px-4 py-2.5">
          <p className="max-w-[76ch] text-hinweis text-muted-foreground">{hint}</p>
        </div>
      )}
      {group.plans.length === 0 && (
        <p className="border-t border-border/70 px-4 py-4 text-hinweis text-muted-foreground">In diesem Themenfeld steht hier kein Plan.</p>
      )}
      {fields.map((f) => (
        <div key={f.key}>
          {f.label && (
            <div className={cn(COLUMNS, "border-t border-border/70 bg-muted/40")}>
              <h4 className="px-4 py-1.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                {f.label} <span className="font-normal">· {f.plans.length}</span>
              </h4>
              <div aria-hidden className={cn(LANE_CELL, "hidden @2xl:block")}>
                <div className="relative h-full"><AxisGrid ticks={axis.ticks} today={axis.today} /></div>
              </div>
            </div>
          )}
          <ul>
            {f.plans.map((plan) => <PlanRow key={plan.key} plan={plan} axis={axis} showField={showField && !f.label} index={index++} stagger={stagger}
              extra={remaining && plan.ends_in ? `noch ${plan.ends_in}` : null} />)}
          </ul>
        </div>
      ))}
    </section>
  );
}

/** Wo man nachfragen kann (§ 3.5): Pläne, zu denen kein aktueller Bericht zu
 *  finden ist. Die Zeile nennt die Tatsache mit Datum, nie eine Wertung, und
 *  bietet die vorbereitete Frage an. Der feste Satz darunter sagt, was
 *  Ratslotse nicht sieht. */
function FollowUps({ items, caveat }: { items: PlanOverview["follow_ups"]; caveat: string }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="plans-follow-ups" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plans-follow-ups">Wo man nachfragen kann</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">{items.length}</p>
      </div>
      <p className="max-w-[76ch] text-hinweis text-muted-foreground">
        Zu diesen Plänen hat Ratslotse keinen aktuellen Bericht im Rat gefunden.
      </p>
      <ul className="mt-2 divide-y divide-border/70">
        {items.map((item) => (
          <li key={item.key} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5">
            <div className="min-w-0 flex-1 basis-64">
              <Link href={planHref(item.key)} prefetch={false}
                className="break-words text-[14px] font-medium leading-snug text-foreground hover:text-primary hover:underline">
                {item.title}
              </Link>
              <p className="mt-0.5 text-meta text-muted-foreground">{item.field_label} · {item.fact}</p>
            </div>
            <Link href={fragenHref({ q: item.question })} prefetch={false}
              className="inline-flex min-h-11 items-center gap-1.5 whitespace-nowrap text-[13px] font-medium text-primary hover:underline">
              <MessageCircleQuestion className="h-4 w-4 shrink-0" aria-hidden /> Den Rat fragen
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-2 max-w-[76ch] text-hinweis text-muted-foreground">{caveat}</p>
    </section>
  );
}

export function PlansView() {
  const { data, loading } = useFetch<PlanOverview>("/council/plans");
  const [field, setField] = useState<string | null>(null);
  const [view, setView] = useState<ViewKey>("status");
  // Sobald einmal sortiert oder gefiltert wurde, gleiten die Zeilen; gestaffelt einlaufen sie nur beim ersten Auftritt.
  const [moved, setMoved] = useState(false);
  const { root, capture } = useFlip<HTMLDivElement>(`${view}|${field ?? ""}`);
  if (loading) return <div className="py-4"><ChartSkeleton bars={6} /></div>;
  if (!data || data.count === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Pläne" hint="Das Register der Pläne ist leer." />;
  }
  const change = (apply: () => void) => { capture(); setMoved(true); apply(); };
  const groups = data.groups
    .map((g) => ({ ...g, plans: field ? g.plans.filter((p) => p.policy_field === field) : g.plans }))
    .filter((g) => g.plans.length > 0);
  const references = field ? data.references.filter((p) => p.policy_field === field) : data.references;
  const chosen = data.views.find((v) => v.key === view) ?? null;
  const byKey = new Map(data.groups.flatMap((g) => g.plans).map((p) => [p.key, p]));
  const ordered = chosen
    ? chosen.plans.map((key) => byKey.get(key)).filter((p): p is PlanCard => !!p && (!field || p.policy_field === field))
    : [];
  return (
    <div className="space-y-5">
      <Stage data={data} />
      <div className="space-y-1.5">
        <FieldChips data={data} field={field} setField={(f) => change(() => setField(f))} />
        <ViewChips views={data.views} view={view} setView={(v) => change(() => setView(v))} />
        <div className="pt-1"><Legend /></div>
      </div>
      <div ref={root} className="space-y-5">
        {chosen ? (
          <GroupCard key={chosen.key} group={{ key: chosen.key, label: chosen.label, plans: ordered }} axis={data.axis}
            splitByField={false} showField={!field} stagger={false} hint={chosen.hint} remaining={chosen.key === "ending"} />
        ) : groups.map((g) => (
          // Nach Feldern gegliedert wird nur die lange Gruppe — und nur, solange kein Feld gewählt ist.
          <GroupCard key={g.key} group={g} axis={data.axis} splitByField={!field && g.plans.length > 12} showField={!field} stagger={!moved} />
        ))}
      </div>
      <FollowUps items={field ? data.follow_ups.filter((f) => f.policy_field === field) : data.follow_ups}
        caveat={data.follow_up_caveat} />
      {references.length > 0 && (
        <section aria-labelledby="plans-references">
          <h3 id="plans-references" className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Auch im Register · Steuerungskonzepte und Pläne Dritter
          </h3>
          <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-card">
            {references.map((plan) => (
              <li key={plan.key}>
                <Link href={planHref(plan.key)} prefetch={false}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50">
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-[14px] font-medium text-foreground">{plan.title}</span>
                    <span className="block text-meta text-muted-foreground">{plan.kicker}</span>
                  </span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
