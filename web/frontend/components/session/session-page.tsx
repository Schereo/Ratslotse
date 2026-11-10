"use client";

/* Die neue Seite einer einzelnen Sitzung (Plan `docs/plan-sitzungsseite-kurs.md`,
   Schritt 3, Schalter `sitzung-kurs`). Drei Ansichten derselben Sitzung —
   vorher, währenddessen, nachher —, ein Aufbau:

   1. Tafel (`.hh-tafel`): Kicker, Kurzname, Aktionen, der gerechnete Satz,
      der „Kurs der Sitzung", „Wichtig in dieser Sitzung".
   2. Tagesordnung als Linie mit Etappen-Bändern und Karten.
   3. Rechts „Ort und Zeit", „Wie es weitergeht", „Quellen" — auf sehr
      breiten Schirmen mit Beschlüssen hat die `BeschlussVorschau` Vorrang
      (Plan 3.7) und die drei Karten rücken unter die Liste.

   Alles, was die heutige Seite trägt, bleibt (Plan 3.6): Zurück, Merken,
   Ratsinfo, Protokoll, LiveChip, Änderungen, Video-Hinweis, Dringliches,
   Anwesenheit, der Sprung zum geteilten Punkt (dieselben `topDomId`). */

import { useMemo, useState, type ReactNode } from "react";
import {
  ArrowDown, ArrowLeft, ArrowRight, ChevronDown, Clock, ExternalLink, MapPin, Navigation, Sparkles,
} from "lucide-react";
import { Course } from "@/components/session/course";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import { VideoResultChip, VideoResultsNotice } from "@/components/video-result";
import { BeschlussVorschau } from "@/components/beschluss-vorschau";
import {
  OUTCOME_DOT_CLS, OUTCOME_FILL_CLS, OUTCOME_RING_CLS, OUTCOME_WORD, OutcomeDot, normalizeParty, partyBrand, voteLabel,
} from "@/components/decision-ui";
import {
  AenderungenSection, AttendanceSection, CalendarButton, LiveChip, ergebnisseJeTop, kurzfassung,
  sessionUrl, topDomId, topKey, videoKey,
} from "@/components/tagesordnung";
import { Aufklapp } from "@/components/aufklapp";
import { courseIcon, COURSE_LOCK_ICON, COURSE_START_ICON } from "@/lib/course-icons";
import type { CourseItem, CourseStage, SessionCourse } from "@/lib/course";
import {
  formalActTitle, groupFormalActs, outcomeCounts, priorStations, sessionKicker, sessionPhase,
  splitNumber, type SessionPhase,
} from "@/lib/session-page";
import { decisionHref, mitlesenHref, punktHref, sitzungHref, sessionHref } from "@/lib/routes";
import { localTodayISO } from "@/lib/live";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { formatDate } from "@/components/ui";
import type { AgendaItem, DecisionOutcome, SessionDetail, VideoResult } from "@/lib/types";
import { cn } from "@/lib/utils";

export type SessionWithCourse = SessionDetail & { course: SessionCourse; live_until?: string | null };

const AKTION = "inline-flex min-h-11 items-center justify-center gap-2 rounded-[11px] border px-4 py-2 text-sm font-medium transition-colors duration-fluss focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0";
const AKTION_PRIMAER = cn(AKTION, "border-primary bg-primary text-primary-foreground hover:bg-primary/90");
const AKTION_SEKUNDAER = cn(AKTION, "border-border bg-card text-foreground hover:bg-accent");
const AKTION_EXTERN = cn(AKTION, "border-dashed border-border bg-card/60 text-foreground hover:bg-accent");
const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";

/** Feste Texte (Plan § 4.6). */
const TEXT = {
  legendeVorher: "Jede Boje ist ein Punkt der Tagesordnung, jedes helle Band eine Etappe der Sitzung. Die großen Bojen sind die wichtigen. Der gelbe Punkt heißt: stand schon einmal hier und wurde vertagt.",
  hinweisVorher: "Kurzfassungen sind automatisch aus Vorlagen und Anträgen erstellt. Verbindlich sind die Unterlagen im Ratsinfo.",
  hinweisNachher: "Kurzfassungen sind automatisch erstellt. Verbindlich ist das Protokoll.",
  anfragen: "Fragen der Mitglieder an die Verwaltung. Ein Beschluss kommt dabei nicht heraus.",
  einwohnerfragen: "Hier können Einwohner*innen dem Ausschuss Fragen stellen.",
  widmung: "Mit einer Widmung wird eine Straße oder ein Weg offiziell zur öffentlichen Straße.",
  formalakt: "Widmung, Einziehung und Umstufung machen einen Zustand amtlich, den es meist schon gibt.",
  gesperrt: "Das Ratsinfo sperrt hier auch die Überschriften. Mehr als die Zahl der Punkte ist nicht öffentlich.",
  nichtoeffentlich: "Nichtöffentlich berät ein Ausschuss, wenn das öffentliche Wohl oder berechtigte Interessen Einzelner es verlangen, zum Beispiel bei Grundstücken, Personal oder Verträgen.",
};

interface Ctx {
  data: SessionWithCourse;
  ksinr: number;
  phase: SessionPhase;
  itemsByNr: Map<string, AgendaItem>;
  course: SessionCourse;
  outcomeByItem: Record<string, DecisionOutcome | null>;
  decisionByItem: Record<string, number>;
  videoByItem: Record<string, VideoResult>;
  voteByItem: Record<string, string | null>;
  /** Nach dem Protokoll: was beschlossen wurde, in einfachen Worten — vor dem
   *  Kartentext, der die Sitzung noch ankündigt („Der Ausschuss berät …"). */
  decisionTextByItem: Record<string, string | null>;
  flashTop: string | null;
  /** Schalter `punkt-seite`: Karten ohne Beschluss führen auf die Seite des Punkts. */
  punktSeite: boolean;
  /** Schalter `mitlesen`: der Einstieg im Kopf (während der Sitzung als Primäraktion). */
  mitlesen: boolean;
}

export function SessionPage({ data, ksinr, flashTop, weit, zurueck }: {
  data: SessionWithCourse;
  ksinr: number;
  flashTop: string | null;
  /** Ab `weit` (1680 px) — dann hat die Beschluss-Vorschau rechts Vorrang. */
  weit: boolean;
  zurueck?: () => void;
}) {
  const course = data.course;
  const phase = sessionPhase(data);
  const { outcomeByItem, decisionByItem, videoByItem } = useMemo(() => ergebnisseJeTop(data), [data]);
  const { voteByItem, decisionTextByItem } = useMemo(() => {
    const votes: Record<string, string | null> = {};
    const texte: Record<string, string | null> = {};
    for (const d of data.decisions ?? []) {
      if (d.kind !== "decision" || !d.item_number) continue;
      const k = topKey(d.item_number);
      votes[k] ??= d.vote ?? null;
      texte[k] ??= d.simple_summary || d.summary || null;
    }
    return { voteByItem: votes, decisionTextByItem: texte };
  }, [data]);
  const itemsByNr = useMemo(() => new Map((data.agenda_items ?? []).map((it) => [it.item_number, it])), [data]);
  const punktSeite = useFeature("punkt-seite");
  const mitlesen = useFeature("mitlesen");
  const ctx: Ctx = { data, ksinr, phase, itemsByNr, course, outcomeByItem, decisionByItem, videoByItem, voteByItem, decisionTextByItem, flashTop, punktSeite, mitlesen };
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const mitBeschluss = Object.values(decisionByItem);
  const vorschauId = weit && mitBeschluss.length > 0 ? (gewaehlt ?? mitBeschluss[0]) : null;
  const videoCount = Object.keys(videoByItem).length;

  return (
    <div className={vorschauId != null ? "mx-auto max-w-[1600px]" : "mx-auto max-w-[1240px]"}>
      {zurueck && (
        <button onClick={zurueck}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
          <ArrowLeft className="h-4 w-4 shrink-0" /> Zurück zu den Sitzungen
        </button>
      )}

      <Board ctx={ctx} />

      {phase === "before" && (data.agenda_changes?.length ?? 0) > 0 && (
        <div className="mt-5"><AenderungenSection aenderungen={data.agenda_changes!} /></div>
      )}

      <div className={cn(
        "mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6",
        vorschauId != null ? "breit:grid-cols-[minmax(0,1fr)_minmax(0,560px)]" : "breit:grid-cols-[minmax(0,1fr)_300px]",
      )}>
        <section aria-labelledby="tagesordnung-titel" className="min-w-0">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 id="tagesordnung-titel" className="font-display text-xl font-bold text-foreground">Tagesordnung</h2>
            <p className={KICKER}>{zaehlung(course)}</p>
          </div>
          {punktSeite && (
            <p className="mt-2 max-w-[46rem] text-[15px] leading-relaxed text-foreground">
              Punkte mit Vorlage oder Antrag haben eine eigene Seite: mit Vorgeschichte und Unterlagen.
            </p>
          )}
          <p className="mt-2 flex gap-2 text-hinweis text-foreground">
            <Sparkles className="mt-1 h-4 w-4 shrink-0 text-signal" aria-hidden />
            {phase === "protocol" ? TEXT.hinweisNachher : TEXT.hinweisVorher}
          </p>
          {videoCount > 0 && phase !== "protocol" && (
            <div className="mt-3">
              <VideoResultsNotice count={videoCount} videoId={Object.values(videoByItem)[0].video_id} />
            </div>
          )}
          {phase === "past" && (
            <p className="mt-3 rounded-xl border border-dashed border-border bg-muted/40 p-3 text-hinweis text-foreground">
              Die Sitzung war am {formatDate(data.session_date)}. Ergebnisse stehen hier, sobald das Protokoll vorliegt.
            </p>
          )}
          <Track ctx={ctx} onVorschau={vorschauId != null ? setGewaehlt : undefined} gewaehltId={vorschauId} />
          <div className="mt-4"><AttendanceSection detail={data} /></div>
          {vorschauId != null && <div className="mt-6 grid gap-4 md:grid-cols-3"><SideCards ctx={ctx} /></div>}
        </section>
        {vorschauId != null ? (
          <BeschlussVorschau key={vorschauId} id={vorschauId} className="sticky top-6" />
        ) : (
          <aside className="flex flex-col gap-4" aria-label="Zur Sitzung"><SideCards ctx={ctx} /></aside>
        )}
      </div>
    </div>
  );
}

function zaehlung(course: SessionCourse): string {
  const teile = [`${course.public_count} öffentlich`];
  if (course.closed_count) teile.push(`${course.closed_count} nichtöffentlich`);
  return teile.join(" · ");
}

// ---------------------------------------------------------------------------
// 1. Tafel

function Board({ ctx }: { ctx: Ctx }) {
  const { data, ksinr, phase, course } = ctx;
  const kurzname = shortCommittee(data.committee);
  const protokollUrl = data.decisions?.find((d) => d.protocol_url)?.protocol_url ?? null;
  const items = data.agenda_items ?? [];
  const hrefFor = useMemo(() => (nr: string) => `#${topDomId(ksinr, nr)}`, [ksinr]);
  const provisional = useMemo(
    () => Object.fromEntries(Object.entries(ctx.videoByItem).map(([k, v]) => [k, v.outcome as DecisionOutcome])),
    [ctx.videoByItem]);
  const results = useMemo(() => ({ outcomeByItem: ctx.outcomeByItem, provisionalByItem: provisional }),
    [ctx.outcomeByItem, provisional]);
  const alleNummern = course.stages.flatMap((s) => s.cells.flatMap((c) => c.items));
  const zaehl = phase === "protocol" ? outcomeCounts(alleNummern, ctx.outcomeByItem) : null;
  const wichtig = alleNummern.filter((nr) => course.items[nr]?.important);

  return (
    <header aria-labelledby="sitzung-titel" className="hh-tafel mt-3 rounded-[18px] p-4 [overflow-wrap:anywhere] sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <p className={KICKER}>{sessionKicker(data)}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
            <h1 id="sitzung-titel" className="font-display text-[28px] font-bold leading-tight tracking-tight text-foreground sm:text-[32px]">
              {kurzname}
            </h1>
            {phase === "live" && <LiveChip />}
          </div>
          {kurzname !== data.committee.trim() && (
            <p className="mt-1 text-meta text-muted-foreground">{data.committee}</p>
          )}
        </div>
        <div role="group" aria-label="Aktionen zur Sitzung" className="flex flex-wrap gap-2">
          {(phase === "before" || phase === "live") && (
            <CalendarButton session={data} agenda={items.map((it) => `${it.item_number} ${it.title}`)}
              className={phase === "before" && !(ctx.mitlesen && data.session_date === localTodayISO()) ? AKTION_PRIMAER : AKTION_SEKUNDAER} />
          )}
          {/* Mitlesen: während der Sitzung die Primäraktion, am Tag davor
              daneben, sonst gar nicht (Plan, Schritt 5). */}
          {ctx.mitlesen && (phase === "live" || (phase === "before" && data.session_date === localTodayISO())) && (
            <a href={mitlesenHref(ksinr)} className={phase === "live" ? AKTION_PRIMAER : AKTION_SEKUNDAER}>
              <Navigation aria-hidden /> Mitlesen
            </a>
          )}
          <BookmarkButton target={{ kind: "session", ksinr }} className={AKTION_SEKUNDAER} />
          <ShareButton path={sitzungHref(ksinr)} label="Sitzung teilen" still
            className={phase === "before" || phase === "live" ? AKTION_SEKUNDAER : AKTION_PRIMAER}
            title={`${data.committee} am ${formatDate(data.session_date)}`} />
          {protokollUrl && (
            <a href={protokollUrl} target="_blank" rel="noreferrer" className={AKTION_EXTERN}>
              Protokoll <ExternalLink aria-hidden />
            </a>
          )}
          <a href={sessionUrl(ksinr)} target="_blank" rel="noreferrer" className={AKTION_EXTERN}>
            Ratsinfo <ExternalLink aria-hidden />
          </a>
        </div>
      </div>

      {course.summary && (
        <div className="mt-5 max-w-[46rem]">
          <p className="text-lese text-foreground">{course.summary}</p>
          <p className="mt-1 text-hinweis text-muted-foreground">
            {phase === "protocol" ? "Aus dem Protokoll gezählt." : "Aus der Tagesordnung gezählt."}
          </p>
        </div>
      )}

      <div className="mt-6 border-t border-border pt-5">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className={KICKER}>Kurs der Sitzung</h2>
          <p className={KICKER}>{zaehlung(course)}</p>
        </div>
        <Course course={course} results={results} hrefFor={hrefFor} />
        {zaehl && zaehl.counts.length > 0 ? (
          <div className="mt-3">
            <p className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-foreground">
              {zaehl.counts.map(([o, n]) => (
                <span key={o} className="inline-flex items-center gap-1.5">
                  <span className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS[o])} aria-hidden />
                  <strong className="font-semibold">{n}</strong> {OUTCOME_WORD[o]}
                </span>
              ))}
            </p>
            <p className="mt-2 max-w-[46rem] text-hinweis text-muted-foreground">
              Die Farbe der Boje zeigt das Ergebnis; {zaehl.withResult} von {course.public_count} öffentlichen Punkten hatten eines.
            </p>
          </div>
        ) : (
          <p className="mt-3 max-w-[46rem] text-hinweis text-muted-foreground">{TEXT.legendeVorher}</p>
        )}
      </div>

      {wichtig.length > 0 && (
        <div className="mt-6 border-t border-border pt-5">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4">
            <h2 className={KICKER}>Wichtig in dieser Sitzung</h2>
            <p className={KICKER}>{wichtig.length} von {course.substantive_count}</p>
          </div>
          <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:snap-none sm:grid-cols-3 sm:overflow-visible sm:px-0">
            {wichtig.map((nr) => <ImportantCard key={nr} ctx={ctx} nr={nr} />)}
          </div>
        </div>
      )}
    </header>
  );
}

function ImportantCard({ ctx, nr }: { ctx: Ctx; nr: string }) {
  const item = ctx.course.items[nr];
  const agenda = ctx.itemsByNr.get(nr);
  const Icon = courseIcon(item.icon);
  const outcome = ctx.outcomeByItem[topKey(nr)] ?? null;
  const text = erstSatz(ctx.decisionTextByItem[topKey(nr)] ?? (agenda ? kurzfassung(agenda) : null)) ?? item.short_title;
  const unten = ctx.phase === "protocol" ? item.short_title : (item.important_reason ?? null);
  const kopf = [nr, outcome ? OUTCOME_WORD[outcome] : item.type_label].filter(Boolean).join(" · ");
  return (
    <article className="flex w-[78%] max-w-[300px] flex-none snap-start flex-col rounded-xl border border-border bg-card p-4 shadow-sm sm:w-auto sm:max-w-none">
      <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.07em] text-muted-foreground">
        <span className={cn("flex h-6 w-6 flex-none items-center justify-center rounded-full",
          outcome ? OUTCOME_FILL_CLS[outcome] : "bg-primary text-primary-foreground")}>
          <Icon className="h-3.5 w-3.5" aria-hidden />
        </span>
        {kopf}
      </p>
      <p className="mt-3 text-[15px] font-semibold leading-snug text-foreground">{text}</p>
      {unten && unten !== text && <p className="mt-2 text-hinweis text-muted-foreground">{unten}</p>}
      <a href={ctx.punktSeite && ctx.decisionByItem[topKey(nr)] == null ? punktHref(ctx.ksinr, nr) : `#${topDomId(ctx.ksinr, nr)}`}
        className="mt-auto inline-flex min-h-11 items-center gap-1.5 pt-3 text-sm font-medium text-primary hover:underline">
        Zum Punkt {ctx.phase === "protocol" ? <ArrowDown className="h-4 w-4" aria-hidden /> : <ArrowRight className="h-4 w-4" aria-hidden />}
      </a>
    </article>
  );
}

function erstSatz(text: string | null | undefined): string | null {
  if (!text) return null;
  const m = text.match(/^(.+?[.!?])(\s|$)/);
  return (m ? m[1] : text).trim();
}

// ---------------------------------------------------------------------------
// 2. Tagesordnung als Linie

function Track({ ctx, onVorschau, gewaehltId }: {
  ctx: Ctx; onVorschau?: (id: number) => void; gewaehltId: number | null;
}) {
  const { course, data } = ctx;
  const stages = course.stages;
  const offen = stages.filter((s) => s.kind !== "closed").length;
  return (
    <ol className="mt-5 [overflow-wrap:anywhere]" aria-label="Tagesordnung nach Etappen">
      <Row rail={<RailMark kind="start" />} line="solid" first>
        <p className="flex min-h-11 items-center gap-2 text-sm">
          <span className="font-mono text-meta uppercase tracking-[0.06em] text-primary">Leinen los</span>
          <span className="text-foreground">{data.session_time ? `Beginn ${data.session_time.slice(0, 5)} Uhr` : "Beginn noch nicht angegeben"}</span>
        </p>
      </Row>
      {stages.map((st, si) => (
        <StageBlock key={si} ctx={ctx} stage={st} index={si} total={stages.length}
          lastOpen={si === offen - 1} onVorschau={onVorschau} gewaehltId={gewaehltId} />
      ))}
    </ol>
  );
}

/** Eine Zeile der Linie: links die Schiene mit Zeichen, rechts der Inhalt. */
function Row({ rail, line, first, last, children, dashedAfter }: {
  rail: ReactNode; line: "solid" | "dashed"; first?: boolean; last?: boolean; dashedAfter?: boolean;
  children: ReactNode;
}) {
  return (
    <li className="grid grid-cols-[40px_minmax(0,1fr)] gap-x-3 sm:grid-cols-[44px_minmax(0,1fr)] sm:gap-x-4">
      <div className="relative flex justify-center">
        {!first && <span aria-hidden className={cn("absolute left-1/2 top-0 h-6 -translate-x-1/2 border-l-2",
          line === "dashed" ? "border-dashed border-primary/30" : "border-primary/30")} />}
        {!last && <span aria-hidden className={cn("absolute bottom-0 left-1/2 top-6 -translate-x-1/2 border-l-2",
          dashedAfter || line === "dashed" ? "border-dashed border-primary/30" : "border-primary/30")} />}
        <div className="relative z-[1] mt-1">{rail}</div>
      </div>
      <div className="min-w-0 pb-3">{children}</div>
    </li>
  );
}

function RailMark({ kind, icon, important, outcome, provisional, postponed }: {
  kind: "start" | "stage" | "item" | "lock"; icon?: string; important?: boolean;
  outcome?: DecisionOutcome | null; provisional?: boolean; postponed?: boolean;
}) {
  if (kind === "start") {
    return <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground">
      <COURSE_START_ICON className="h-4 w-4" strokeWidth={2.5} aria-hidden /></span>;
  }
  if (kind === "stage") {
    return <span className="mt-3 block h-3.5 w-3.5 rounded-full border-2 border-primary bg-background" aria-hidden />;
  }
  if (kind === "lock") {
    return <span className="flex h-8 w-8 items-center justify-center rounded-full border border-dashed border-muted-foreground/55 bg-background text-muted-foreground">
      <COURSE_LOCK_ICON className="h-4 w-4" aria-hidden /></span>;
  }
  const Icon = courseIcon(icon);
  const size = important ? "h-10 w-10 sm:h-11 sm:w-11" : "h-8 w-8";
  return (
    <span className={cn("relative flex items-center justify-center rounded-full", size,
      important
        ? (outcome && !provisional ? OUTCOME_FILL_CLS[outcome] : "bg-primary text-primary-foreground")
        : cn("bg-card text-muted-foreground", outcome ? cn("border-2", ringFor(outcome)) : "border border-primary/35",
            provisional && "border-dashed"))}>
      <Icon className={important ? "h-5 w-5" : "h-4 w-4"} aria-hidden />
      {postponed && <span aria-hidden className={cn("absolute -right-0.5 -top-0.5 h-[11px] w-[11px] rounded-full border-2 border-background", OUTCOME_DOT_CLS.postponed)} />}
    </span>
  );
}

const ringFor = (o: DecisionOutcome) => OUTCOME_RING_CLS[o];

function StageBlock({ ctx, stage, index, total, lastOpen, onVorschau, gewaehltId }: {
  ctx: Ctx; stage: CourseStage; index: number; total: number; lastOpen: boolean;
  onVorschau?: (id: number) => void; gewaehltId: number | null;
}) {
  if (stage.kind === "closed") {
    return (
      <Row rail={<RailMark kind="lock" />} line="dashed" last>
        <div className="rounded-xl border border-dashed border-border p-4">
          <StageHead stage={stage} index={index} total={total} count={`${stage.range} · ${stage.count} ${stage.count === 1 ? "Punkt" : "Punkte"}`} bare />
          <p className="mt-2 text-hinweis text-foreground">{TEXT.gesperrt}</p>
          <LottiErklaert className="mt-3" title="Lotti erklärt's einfach" text={TEXT.nichtoeffentlich} />
        </div>
      </Row>
    );
  }
  const nummern = stage.cells.flatMap((c) => c.items);
  const zaehl = stage.kind === "motions"
    ? `${stage.range} · ${nummern.length} ${nummern.length === 1 ? "Antrag" : "Anträge"}`
    : `${stage.range} · ${stage.count} ${stage.count === 1 ? "Punkt" : "Punkte"}`;
  // Karten der Etappe: die Formalien als eine (so kommen sie vom Server),
  // gleichartige Formalakte direkt hintereinander zusammen.
  const zusammen: string[][] = stage.cells.some((c) => c.title)
    ? stage.cells.map((c) => (c.title ? c.items : [c.items[0]]))
    : groupFormalActs(stage.cells.map((c) => c.items[0]), (nr) => !!ctx.course.items[nr]?.formal_act);
  const formalLabel = stage.cells.find((c) => c.title)?.label ?? null;
  const letzteKarte = zusammen.length - 1;
  return (
    <>
      <Row rail={<RailMark kind="stage" />} line="solid">
        <StageHead stage={stage} index={index} total={total} count={zaehl} />
      </Row>
      {zusammen.map((g, gi) => {
        const formal = g.length > 1 && !!ctx.course.items[g[0]]?.formality;
        const akte = g.length > 1 && !formal;
        const erste = ctx.course.items[g[0]];
        const dashedAfter = lastOpen && gi === letzteKarte;
        return (
          <Row key={g.join("|")} line="solid" dashedAfter={dashedAfter}
            rail={<RailMark kind="item" icon={formal ? "formalities" : erste?.icon} important={!formal && !akte && erste?.important}
              outcome={formal || akte ? null : (ctx.outcomeByItem[topKey(g[0])] ?? null)}
              provisional={!formal && !akte && !ctx.outcomeByItem[topKey(g[0])] && !!ctx.videoByItem[videoKey(g[0])]}
              postponed={!formal && !akte && (erste?.postponed ?? 0) > 0} />}>
            {formal ? <FormalitiesCard ctx={ctx} nrs={g} label={formalLabel ?? g[0]} />
              : akte ? <FormalActCard ctx={ctx} nrs={g} onVorschau={onVorschau} />
              : <ItemCard ctx={ctx} nr={g[0]} onVorschau={onVorschau} gewaehlt={gewaehltId != null && ctx.decisionByItem[topKey(g[0])] === gewaehltId} />}
          </Row>
        );
      })}
    </>
  );
}

function StageHead({ stage, index, total, count, bare }: {
  stage: CourseStage; index: number; total: number; count: string; bare?: boolean;
}) {
  return (
    <div className={cn(!bare && "rounded-xl border border-primary/20 bg-primary/[0.07] px-4 py-3")}>
      <p className={KICKER}>Etappe {index + 1} von {total}</p>
      <div className="mt-0.5 flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <h3 className="font-display text-lg font-semibold leading-snug text-foreground">{stage.name}</h3>
          {stage.subtitle && <p className="text-hinweis text-muted-foreground">{stage.subtitle}</p>}
        </div>
        <p className={KICKER}>{count}</p>
      </div>
    </div>
  );
}

/** Die große Nummer: „Ö" in Muted, die Zahl in Text (Bricolage 26). */
function BigNumber({ nr, strong }: { nr: string; strong?: boolean }) {
  const { prefix, rest } = splitNumber(nr);
  return (
    <p className="font-display text-[26px] font-bold leading-none tabular-nums" aria-hidden>
      {prefix && <span className="text-muted-foreground">{prefix} </span>}
      <span className={strong ? "text-primary" : "text-foreground"}>{rest}</span>
    </p>
  );
}

function Chip({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "outline" | "primary" | "amber" }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
      tone === "outline" && "border border-border bg-card text-foreground",
      tone === "muted" && "rounded-full border border-border bg-muted text-muted-foreground",
      tone === "primary" && "bg-primary/10 text-foreground",
      tone === "amber" && "border border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
    )}>{children}</span>
  );
}

function ItemCard({ ctx, nr, onVorschau, gewaehlt }: {
  ctx: Ctx; nr: string; onVorschau?: (id: number) => void; gewaehlt: boolean;
}) {
  const item: CourseItem | undefined = ctx.course.items[nr];
  const agenda = ctx.itemsByNr.get(nr);
  if (!item || !agenda) return null;
  const key = topKey(nr);
  const outcome = ctx.outcomeByItem[key] ?? null;
  const decisionId = ctx.decisionByItem[key];
  const video = outcome ? undefined : ctx.videoByItem[videoKey(nr)];
  const vote = ctx.voteByItem[key];
  const domId = topDomId(ctx.ksinr, nr);
  const nachher = ctx.phase === "protocol";
  const offen = item.important && nachher;
  const frame = item.type === "question_time" || item.type === "inquiries" || item.type === "announcement";
  const gremium = /^rat\b/i.test(ctx.data.committee.trim()) ? "dem Rat" : "dem Ausschuss";
  const text = frame
    ? (item.type === "question_time" ? TEXT.einwohnerfragen.replace("dem Ausschuss", gremium)
      : item.type === "inquiries" ? TEXT.anfragen : kurzfassung(agenda))
    : (ctx.decisionTextByItem[key] ?? kurzfassung(agenda));
  const frueher = priorStations(item.journey, ctx.ksinr, ctx.data.session_date);
  const anlagen = agenda.anlagen?.length ?? 0;
  const vorlageUrl = agenda.kvonr ? `https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=${agenda.kvonr}` : null;
  const partei = item.applicant ? normalizeParty(item.applicant) : null;
  const brand = partei ? partyBrand(partei) : null;
  const zurSeite = ctx.punktSeite && decisionId == null && !frame;

  return (
    <article id={domId}
      className={cn("@container relative rounded-xl border bg-card p-4 shadow-sm transition-shadow duration-weg",
        zurSeite && "hover:border-primary/45",
        item.important ? "border-primary/45 ring-1 ring-primary/20" : "border-border",
        ctx.flashTop === domId && "ring-2 ring-primary",
        gewaehlt && "ring-2 ring-primary")}>
      <div className="flex flex-col gap-2 @md:flex-row @md:gap-4">
        <div className="whitespace-nowrap @md:min-w-[78px] @md:flex-none"><BigNumber nr={nr} strong={item.important} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {outcome && (
              <span className="inline-flex items-center gap-1 text-sm">
                <OutcomeDot outcome={outcome} />
                {vote && <span className="text-sm text-muted-foreground">· {voteLabel(vote)}</span>}
              </span>
            )}
            {video && <VideoResultChip r={video} />}
            {item.type_label && !frame && <Chip tone="outline">{item.type_label}</Chip>}
            {frame && item.type === "question_time" && <Chip tone="outline">Fragestunde</Chip>}
            {item.important && <Chip tone="primary">Wichtig</Chip>}
            {!item.important && item.postponed > 0 && (
              <Chip tone="amber">{item.postponed === 1 ? "Schon einmal vertagt" : `${item.postponed}-mal vertagt`}</Chip>
            )}
            {agenda.template_number && <span className={KICKER}>Vorlage {agenda.template_number}</span>}
            {agenda.dringlich && <span className={cn(KICKER, "text-signal")}>Dringlichkeitsantrag</span>}
          </div>
          <h4 className="mt-1.5 text-[17px] font-semibold leading-snug text-foreground [hyphens:auto] [overflow-wrap:anywhere] [hyphenate-limit-chars:14_5_5]" lang="de">
            {zurSeite ? (
              // Die ganze Karte ist der Link (Plan § 4.2) — über eine
              // gestreckte Fläche, damit Links darin bedienbar bleiben.
              <a href={punktHref(ctx.ksinr, nr)} className="after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring">
                {item.short_title}
              </a>
            ) : item.short_title}
          </h4>
          {item.applicant && (
            <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
              {brand && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: brand.bg }} aria-hidden />}
              <span className="font-semibold text-foreground">{item.applicant}</span>
            </p>
          )}
          {text && (!item.important || !nachher || offen) && (
            <p className={cn("mt-2 text-foreground", offen ? "text-lese" : "text-[15px] leading-relaxed text-foreground")}>
              {text}
            </p>
          )}
          {item.important && item.important_reason && !nachher && (
            <p className="mt-2 text-hinweis text-foreground">
              <strong className="font-semibold">Wichtig:</strong> {item.important_reason}
            </p>
          )}
          {offen && item.journey.length > 1 && <Journey ctx={ctx} item={item} />}
          {item.next_on_agenda && (
            <div className="mt-3 rounded-xl border border-primary/20 bg-primary/[0.06] p-3">
              <p className={KICKER}>Wie es weitergeht</p>
              <p className="mt-1 text-sm text-foreground">
                Der Punkt steht am {formatDate(item.next_on_agenda.session_date)} wieder auf der Tagesordnung
                {" "}({item.next_on_agenda.item_number}).
              </p>
              <a href={sitzungHref(item.next_on_agenda.ksinr, [item.next_on_agenda.item_number])}
                className="relative z-[1] mt-1 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                Zur Sitzung am {formatDate(item.next_on_agenda.session_date)} <ArrowRight className="h-4 w-4" aria-hidden />
              </a>
            </div>
          )}
          {!nachher && (frueher.length > 0 || anlagen > 0) && (
            <p className="mt-3 flex flex-wrap gap-1.5">
              {frueher.length > 0 && <Chip>Vorgeschichte <strong className="font-semibold text-foreground">{frueher.length} {frueher.length === 1 ? "Station" : "Stationen"}</strong></Chip>}
              {anlagen > 0 && <Chip>Unterlagen <strong className="font-semibold text-foreground">{anlagen} {anlagen === 1 ? "Dokument" : "Dokumente"}</strong></Chip>}
            </p>
          )}
          {agenda.anlagen && agenda.anlagen.length > 0 && frame && (
            <ul className="mt-2 space-y-1">
              {agenda.anlagen.map((a, i) => (
                <li key={i}><a href={a.url} target="_blank" rel="noreferrer"
                  className="relative z-[1] inline-flex min-h-11 items-center gap-1.5 text-sm text-primary hover:underline">
                  {a.label} <ExternalLink className="h-3.5 w-3.5" aria-hidden /></a></li>
              ))}
            </ul>
          )}
          {(decisionId != null || (item.type === "motion" && vorlageUrl)) && (
            <p className="mt-2 flex flex-wrap gap-x-5">
              {decisionId != null && (
                <a href={decisionHref(decisionId)}
                  onClick={onVorschau ? (e) => { if (!e.metaKey && !e.ctrlKey) { e.preventDefault(); onVorschau(decisionId); } } : undefined}
                  className="relative z-[1] inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  Zum Beschluss <ArrowRight className="h-4 w-4" aria-hidden />
                </a>
              )}
              {item.type === "motion" && vorlageUrl && (
                <a href={vorlageUrl} target="_blank" rel="noreferrer"
                  className="relative z-[1] inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  Antrag im Ratsinfo <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                </a>
              )}
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

function Journey({ ctx, item }: { ctx: Ctx; item: CourseItem }) {
  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <p className={KICKER}>Der Weg dieser Vorlage</p>
        <p className={KICKER}>{item.journey.length} Stationen</p>
      </div>
      <ol className="mt-2 flex flex-wrap items-center gap-2">
        {item.journey.map((s, i) => {
          const hier = s.ksinr === ctx.ksinr;
          const o = s.outcome as DecisionOutcome | null;
          return (
            <li key={`${s.ksinr}-${i}`} className="flex items-center gap-2">
              {i > 0 && <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
              <a href={hier ? undefined : sessionHref(s.ksinr)}
                className={cn("block rounded-lg border px-3 py-1.5 text-sm",
                  hier ? "border-primary/30 bg-primary/[0.08]" : "border-border bg-card hover:bg-accent")}>
                <span className="block font-medium text-foreground">{shortCommittee(s.committee)}</span>
                <span className="flex items-center gap-1.5 text-meta text-muted-foreground">
                  {formatDate(s.session_date)}
                  {hier ? <span className="text-primary">· diese Sitzung</span>
                    : o && <><span className={cn("h-1.5 w-1.5 rounded-full", OUTCOME_DOT_CLS[o])} aria-hidden />{OUTCOME_WORD[o].toLowerCase()}</>}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function FormalitiesCard({ ctx, nrs, label }: { ctx: Ctx; nrs: string[]; label: string }) {
  const [offen, setOffen] = useState(false);
  const titel = nrs.map((nr) => ctx.itemsByNr.get(nr)?.title ?? "");
  const teile: string[] = [];
  if (titel.some((t) => /beschlussf/i.test(t))) teile.push("Beschlussfähigkeit");
  if (titel.some((t) => /tagesordnung/i.test(t))) teile.push("Tagesordnung");
  const protokolle = titel.filter((t) => /protokoll/i.test(t) && /Nr\./.test(t)).length;
  if (protokolle || titel.some((t) => /protokoll/i.test(t))) teile.push(protokolle > 1 ? "Protokolle" : "Protokoll");
  return (
    <article id={topDomId(ctx.ksinr, nrs[0])} className="@container rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <div className="flex flex-col gap-x-4 gap-y-1 @md:flex-row @md:items-center">
        <div className="whitespace-nowrap @md:min-w-[78px]"><BigNumber nr={label} /></div>
        <div className="min-w-0 flex-1">
          <h4 className="text-[17px] font-semibold text-foreground">Formalien</h4>
          <p className="text-sm text-muted-foreground">{teile.join(", ")}.</p>
        </div>
        <button type="button" onClick={() => setOffen((o) => !o)} aria-expanded={offen}
          className="-ml-2 inline-flex min-h-11 items-center gap-1 self-start rounded-lg px-2 text-sm font-medium text-primary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring @md:ml-0 @md:self-auto">
          {nrs.length} Punkte {offen ? "verbergen" : "zeigen"}
          <ChevronDown className={cn("h-4 w-4 transition-transform duration-fluss", offen && "rotate-180")} aria-hidden />
        </button>
      </div>
      <Aufklapp offen={offen}>
        <ul className="mt-2 divide-y divide-border/60 border-t border-border/60">
          {nrs.map((nr) => (
            <li key={nr} id={nr === nrs[0] ? undefined : topDomId(ctx.ksinr, nr)} className="flex gap-3 py-2 text-sm">
              <span className="w-12 flex-none font-mono text-muted-foreground">{nr}</span>
              <span className="text-foreground">{ctx.itemsByNr.get(nr)?.title}</span>
            </li>
          ))}
        </ul>
      </Aufklapp>
    </article>
  );
}

function FormalActCard({ ctx, nrs, onVorschau }: { ctx: Ctx; nrs: string[]; onVorschau?: (id: number) => void }) {
  const titel = nrs.map((nr) => ctx.itemsByNr.get(nr)?.title ?? "");
  const erste = ctx.course.items[nrs[0]];
  const ergebnisse = nrs.map((nr) => ctx.outcomeByItem[topKey(nr)] ?? null);
  const alleGleich = ergebnisse.every((o) => o && o === ergebnisse[0]);
  const nurWidmung = titel.every((t) => /widmung/i.test(t)) && !titel.some((t) => /einziehung/i.test(t));
  return (
    <article className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {alleGleich && ergebnisse[0] && <OutcomeDot outcome={ergebnisse[0]} />}
        {erste?.type_label && <Chip tone="outline">{erste.type_label}</Chip>}
        <span className={KICKER}>{nrs[0]} – {nrs[nrs.length - 1]} · {nrs.length} Vorlagen</span>
      </div>
      <h4 className="mt-1.5 text-[17px] font-semibold text-foreground">{formalActTitle(titel)}</h4>
      <p className="mt-1 text-sm text-muted-foreground">{nurWidmung ? TEXT.widmung : TEXT.formalakt}</p>
      <ul className="mt-3 divide-y divide-border/60 border-t border-border/60">
        {nrs.map((nr, i) => {
          const agenda = ctx.itemsByNr.get(nr);
          const item = ctx.course.items[nr];
          const decisionId = ctx.decisionByItem[topKey(nr)];
          const domId = topDomId(ctx.ksinr, nr);
          const inhalt = (
            <>
              <span className="w-14 flex-none font-display text-lg font-bold text-foreground">
                <span className="text-muted-foreground">{splitNumber(nr).prefix} </span>{splitNumber(nr).rest}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-foreground">{item?.short_title}</span>
                <span className="block text-sm text-muted-foreground">
                  {[agenda?.template_number ? `Vorlage ${agenda.template_number}` : null, agenda ? kurzfassung(agenda) : null].filter(Boolean).join(" · ")}
                </span>
              </span>
              {!alleGleich && ergebnisse[i] && <OutcomeDot outcome={ergebnisse[i]} />}
              {decisionId != null && <ArrowRight className="h-4 w-4 flex-none text-muted-foreground" aria-hidden />}
            </>
          );
          return (
            <li key={nr} id={domId} className={cn(ctx.flashTop === domId && "rounded-lg ring-2 ring-primary")}>
              {decisionId != null ? (
                <a href={decisionHref(decisionId)}
                  onClick={onVorschau ? (e) => { if (!e.metaKey && !e.ctrlKey) { e.preventDefault(); onVorschau(decisionId); } } : undefined}
                  className="flex min-h-11 items-start gap-3 py-2 hover:bg-accent/50">{inhalt}</a>
              ) : (
                <div className="flex min-h-11 items-start gap-3 py-2">{inhalt}</div>
              )}
            </li>
          );
        })}
      </ul>
    </article>
  );
}

// ---------------------------------------------------------------------------
// 3. Rechte Spalte

function SideCards({ ctx }: { ctx: Ctx }) {
  const { data, phase, ksinr, course } = ctx;
  const datum = new Date(`${data.session_date}T12:00:00`).toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  const protokollUrl = data.decisions?.find((d) => d.protocol_url)?.protocol_url ?? null;
  const next = course.next_session;
  const karte = "rounded-xl border border-border bg-card p-4 shadow-sm";
  return (
    <>
      <section className={karte} aria-labelledby="ort-zeit">
        <h2 id="ort-zeit" className="font-display text-base font-semibold text-foreground">Ort und Zeit</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <div className="flex gap-2.5">
            <dt><Clock className="mt-0.5 h-4 w-4 text-muted-foreground" aria-label="Termin" /></dt>
            <dd><span className="block font-medium text-foreground">{datum}</span>
              <span className="text-muted-foreground">{data.session_time ? `Beginn ${data.session_time.slice(0, 5)} Uhr` : "Uhrzeit noch nicht angegeben"}</span></dd>
          </div>
          <div className="flex gap-2.5">
            <dt><MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" aria-label="Ort" /></dt>
            <dd className="font-medium text-foreground [overflow-wrap:anywhere]">{data.location || <span className="font-normal text-muted-foreground">Ort noch nicht angegeben</span>}</dd>
          </div>
        </dl>
        {phase !== "protocol" && <p className="mt-3 text-sm text-muted-foreground">Der öffentliche Teil ist für alle offen.</p>}
      </section>

      <section className={karte} aria-labelledby="wie-weiter">
        <p className={KICKER}>Wie es weitergeht</p>
        {phase === "protocol" ? (
          <>
            <h2 id="wie-weiter" className="mt-1 font-display text-base font-semibold text-foreground">
              Nächste Sitzung {next ? `des Gremiums` : ""}
            </h2>
            {next ? (
              <div className="mt-2 text-sm">
                <p className="text-foreground">{formatDate(next.session_date)}{next.session_time ? ` · ${next.session_time.slice(0, 5)} Uhr` : ""}</p>
                {next.location && <p className="text-muted-foreground">{next.location}</p>}
                <p className="mt-2 text-muted-foreground">{next.has_agenda ? "Die Tagesordnung liegt vor." : "Die Tagesordnung liegt noch nicht vor."}</p>
                <a href={sessionHref(next.ksinr)} className="mt-1 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary hover:underline">
                  Zur Sitzung <ArrowRight className="h-4 w-4" aria-hidden /></a>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">Eine weitere Sitzung dieses Gremiums steht noch nicht im Kalender.</p>
            )}
          </>
        ) : (
          <>
            <h2 id="wie-weiter" className="mt-1 font-display text-base font-semibold text-foreground">Wann es Ergebnisse gibt</h2>
            <ol className="mt-3 space-y-3 border-l-2 border-primary/30 pl-4 text-sm">
              <li className="relative"><span aria-hidden className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-primary" />
                <span className="block font-medium text-foreground">Sitzung am {formatDate(data.session_date)}</span>
                <span className="text-muted-foreground">Bis dahin erklärt diese Seite, worum es geht.</span></li>
              <li className="relative"><span aria-hidden className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-primary/50 bg-card" />
                <span className="block font-medium text-foreground">Protokoll</span>
                <span className="text-muted-foreground">Kommt meist erst einige Wochen später.</span></li>
              <li className="relative"><span aria-hidden className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-primary/50 bg-card" />
                <span className="block font-medium text-foreground">Ergebnisse auf dieser Seite</span>
                <span className="text-muted-foreground">Dann steht an jedem Punkt, was beschlossen wurde.</span></li>
            </ol>
          </>
        )}
      </section>

      <section className={karte} aria-labelledby="quellen">
        <p id="quellen" className={KICKER}>Quellen</p>
        <ul className="mt-2 space-y-2">
          {protokollUrl && (
            <li><a href={protokollUrl} target="_blank" rel="noreferrer"
              className="block rounded-lg border border-dashed border-border p-3 hover:bg-accent">
              <span className="flex items-center justify-between gap-2 text-quelle font-medium text-foreground">Protokoll der Sitzung <ExternalLink className="h-4 w-4 text-muted-foreground" aria-hidden /></span>
              <span className="text-meta text-muted-foreground">PDF im Ratsinfo der Stadt Oldenburg</span></a></li>
          )}
          <li><a href={sessionUrl(ksinr)} target="_blank" rel="noreferrer"
            className="block rounded-lg border border-dashed border-border p-3 hover:bg-accent">
            <span className="flex items-center justify-between gap-2 text-quelle font-medium text-foreground">Sitzung im Ratsinfo <ExternalLink className="h-4 w-4 text-muted-foreground" aria-hidden /></span>
            <span className="text-meta text-muted-foreground">Tagesordnung, Vorlagen und Anlagen</span></a></li>
        </ul>
      </section>
    </>
  );
}
