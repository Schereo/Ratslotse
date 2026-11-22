"use client";

// WAS DER PLAN FESTLEGT: ein Satz zum Zweck, darunter die Kernpunkte nach Art —
// Ziele oben, Zahlen als Kacheln, dann Regeln, dann Vorhaben und Termine.
// Steht direkt unter dem Kopf: Wer die Seite öffnet, soll den Plan in zwanzig
// Sekunden verstehen, ohne die Beschlüsse zu lesen. Die Gliederung kommt fertig
// aus council/plan_pages.py; hier wird gezeichnet.
//
// Die Sätze hat ein Sprachmodell entworfen; gezeigt wird nur, was als
// wörtliches Zitat in der Quelle steht (council/plan_judge.py). Deshalb
// trägt jeder Satz seinen Beleg: ein Tipp klappt das Zitat auf, der Link
// führt zum Dokument. Wo ein späterer Beschluss den Punkt gesetzt hat,
// steht dessen Datum dabei — der Satz gilt ab dann, nicht seit dem Plan.
//
// Die Zahl einer Kachel und ihr kurzes Wort sind von Hand gesetzt; jede Ziffer
// steht im Zitat (plan_judge.check_extras). Eine Kachel zeigt, was der Plan
// festlegt oder annimmt — nie, was daraus geworden ist (Plan § 3.4).

import { createContext, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, ExternalLink, Sparkles } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { frageLink } from "@/components/frage-chips";
import { Mascot } from "@/components/mascot";
import { Kicker } from "@/components/plans/parts";
import { Quote } from "@/components/plans/quoted";
import { chipMerken } from "@/lib/chip-frage";
import { decisionHref } from "@/lib/routes";
import type { PlanContent, PlanContentGroup, PlanContentStatement, PlanPlain } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** „Rahmenkonzept …, S. 5“ · „Beschluss des Rates vom 16.12.2019“ · „Vorlage der Verwaltung 19/0943“.
 *  `dated`: Das Datum steht schon im Abzeichen daneben. */
export function sourceLine(source: PlanContentStatement["source"], dated = false): string {
  if (source.kind === "attachment") return source.page ? `${source.label}, S. ${source.page}` : source.label;
  if (source.kind === "decision") return source.date_label && !dated ? `${source.label} vom ${source.date_label}` : source.label;
  return `${source.label} ${source.template_number}`;
}

function Evidence({ statement, withText = false }: { statement: PlanContentStatement; withText?: boolean }) {
  const { source } = statement;
  return (
    <div className="pb-3 pl-0 pr-7">
      {withText && (
        // Die Kachel trägt nur Zahl und Stichwort — hier stehen der ganze Satz und seine Quelle.
        <div className="mb-2 max-w-[76ch]">
          <p className="break-words text-[14.5px] leading-snug text-foreground">{statement.text}</p>
          <SourceMeta statement={statement} />
        </div>
      )}
      <Quote text={statement.quote} />
      <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 pl-3 text-meta text-muted-foreground">
        {source.decision_id != null && (
          <Link href={decisionHref(source.decision_id)} prefetch={false} className="font-medium text-primary hover:underline">
            Beschluss ansehen
          </Link>
        )}
        {source.url && (
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {source.kind === "attachment" ? "Dokument öffnen" : `Vorlage ${source.template_number}`}
            <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px" aria-hidden />
          </a>
        )}
        {source.kind === "attachment" && <span className="font-mono">Anlage zu {source.template_number}</span>}
      </p>
    </div>
  );
}

/** Stammt der ganze Block aus EINEM späteren Beschluss, steht dessen Datum einmal am Kopf des Blocks. */
const SharedAsOf = createContext(false);

/** Wo ein späterer Beschluss den Punkt gesetzt hat, steht dessen Datum dabei: Der Satz gilt ab dann. */
function AsOf({ statement }: { statement: PlanContentStatement }) {
  const shared = useContext(SharedAsOf);
  if (shared || !statement.amended || !statement.source.date_label) return null;
  return (
    <span className="inline-flex items-center whitespace-nowrap rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
      Stand {statement.source.date_label}
    </span>
  );
}

function SourceMeta({ statement }: { statement: PlanContentStatement }) {
  const shared = useContext(SharedAsOf);
  const dated = !shared && statement.amended && !!statement.source.date_label;
  return (
    <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted-foreground">
      <AsOf statement={statement} />
      <span className="min-w-0 break-words">{sourceLine(statement.source, dated)}</span>
    </span>
  );
}

const pointId = (index: number | null) => (index == null ? undefined : `plan-point-${index}`);

function Statement({ statement, lead = false, marked = false }: {
  statement: PlanContentStatement; lead?: boolean; marked?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div id={pointId(statement.index)}
      className={cn("scroll-mt-32 rounded-lg transition-colors duration-buehne ease-out-strong", marked && "bg-primary/[0.08]")}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 py-2.5 text-left hover:bg-primary/[0.03]">
        <span className="min-w-0">
          {statement.tag && (
            <span className="mb-0.5 block font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{statement.tag}</span>
          )}
          <span className={cn("block break-words text-foreground",
            lead ? "text-[16px] font-medium leading-snug sm:text-[17px]" : "text-[14.5px] leading-snug")}>
            {statement.text}
          </span>
          <SourceMeta statement={statement} />
        </span>
        <span className="mt-0.5 flex items-center gap-1 text-meta text-muted-foreground">
          <span className="hidden sm:inline">{open ? "Zitat zu" : "Zitat"}</span>
          <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
        </span>
      </button>
      <Aufklapp offen={open}><Evidence statement={statement} /></Aufklapp>
    </div>
  );
}

/** Spalten je Anzahl, damit keine Zeile ein Loch lässt: schmal zwei (bei ungerader Zahl nimmt die
 *  erste Kachel die ganze Zeile), breit so viele, wie da sind — vier nebeneinander erst ab breiter Karte. */
const TILE_COLUMNS: Record<number, string> = {
  1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-2 @2xl:grid-cols-3", 4: "grid-cols-2 @4xl:grid-cols-4",
  5: "grid-cols-2 @2xl:grid-cols-6", 6: "grid-cols-2 @2xl:grid-cols-3",
};

/** Die Zahlen als Kacheln: groß die Ziffer, darunter in wenigen Worten, was sie
 *  zählt. Ein Tipp zeigt unter der Reihe den ganzen Satz mit Zitat — eine Kachel
 *  offen, nicht mehrere, sonst stünde das Zitat fern von seiner Zahl. */
function Tiles({ group, marked }: { group: PlanContentGroup; marked: number | null }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const open = group.points.find((p) => p.index === openIndex) ?? null;
  const count = group.points.length;
  const single = count === 1;
  return (
    <div>
      <ul className={cn("grid gap-2", TILE_COLUMNS[count] ?? "grid-cols-2 @2xl:grid-cols-3")}>
        {group.points.map((point, i) => {
          const isOpen = point.index === openIndex;
          return (
            <li key={point.index} id={pointId(point.index)}
              className={cn("min-w-0 scroll-mt-32",
                // Ungerade Zahl: schmal füllt die erste die Zeile; bei fünf stehen breit zwei über drei.
                count % 2 === 1 && count > 1 && i === 0 && (count === 3 ? "col-span-2 @2xl:col-span-1" : "col-span-2"),
                count === 5 && (i < 2 ? "@2xl:col-span-3" : "@2xl:col-span-2"))}>
              <button type="button" aria-expanded={isOpen}
                onClick={() => setOpenIndex(isOpen ? null : point.index)}
                className={cn("flex h-full w-full min-w-0 rounded-[10px] border px-3 py-2.5 text-left transition-colors duration-fluss ease-out-strong",
                  single ? "flex-wrap items-baseline gap-x-4 gap-y-1" : "flex-col",
                  isOpen ? "border-primary/50 bg-primary/[0.06]" : "border-border/70 bg-card hover:border-primary/40",
                  marked === point.index && "bg-primary/[0.08]")}>
                <span className="block max-w-full break-words font-display text-[22px] font-bold leading-none tabular-nums text-foreground sm:text-[28px]">
                  {point.figure?.value}
                </span>
                <span className={cn("min-w-0", single ? "flex-1 basis-48" : "mt-1.5 flex w-full flex-1 flex-col")}>
                  <span className="block hyphens-auto break-words text-[13.5px] leading-snug text-foreground">{point.figure?.label}</span>
                  <span className={cn("flex items-end justify-between gap-2", single ? "mt-1" : "mt-auto pt-1")}>
                    <span className="min-w-0"><AsOf statement={point} /></span>
                    <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-weg ease-in-out-strong", isOpen && "rotate-180")} aria-hidden />
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <Aufklapp offen={open != null}>
        {open && <div className="pt-3"><Evidence statement={open} withText /></div>}
      </Aufklapp>
    </div>
  );
}

function Group({ group, marked }: { group: PlanContentGroup; marked: number | null }) {
  return (
    <div>
      <h3 className="mb-1 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{group.label}</h3>
      {group.layout === "tiles" ? <Tiles group={group} marked={marked} /> : (
        <ul className="max-w-[76ch] divide-y divide-border/70 border-y border-border/70">
          {group.points.map((point) => (
            <li key={point.index}><Statement statement={point} marked={marked === point.index} /></li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** „Lotti erklärt's einfach“ — der Plan in drei Sätzen, entstanden NUR aus den belegten Kernpunkten
 *  darunter (scripts/plan_einfach.py). Zugeklappt: Der Zweck-Satz und die Kernpunkte sagen dasselbe
 *  schon knapp; wer es noch einfacher will, holt es sich mit einem Tipp. Dieselbe Tönung wie auf der
 *  Beschluss-Seite, damit man Lottis Stimme wiedererkennt. */
function Plain({ plain }: { plain: PlanPlain }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-3 rounded-xl border border-signal/30 bg-gradient-to-br from-signal/[0.07] to-transparent">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-2.5 px-3 py-2 text-left">
        <Mascot pose="point" decorative className="h-8 w-8 shrink-0" />
        <span className="min-w-0 flex-1 font-mono text-meta font-medium uppercase tracking-[0.08em] text-orange-800 dark:text-orange-300">
          Lotti erklärt&rsquo;s einfach
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
      </button>
      <Aufklapp offen={open}>
        <div className="max-w-[76ch] px-3 pb-3">
          <ul className="space-y-1.5">
            {plain.sentences.map((sentence) => (
              <li key={sentence} className="break-words text-[15px] leading-snug text-foreground">{sentence}</li>
            ))}
          </ul>
          <p className="mt-2 text-hinweis text-muted-foreground">{plain.note}</p>
        </div>
      </Aufklapp>
    </div>
  );
}

/** Drei Fragen, die „Frag den Rat“ vorbelegt öffnen — derselbe Weg wie die Frage-Chips
 *  (components/frage-chips.tsx), aber als Zeilen: Die Fragen nennen den Plan beim Namen und sind
 *  dafür zu lang für eine Pille (auf dem Handy drei Zeilen in einer Kapsel). */
function Questions({ questions }: { questions: readonly string[] }) {
  return (
    <div role="group" aria-label="Fragen an Lotti" className="mt-4 border-t border-border/70 pt-3.5">
      <p className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 text-signal" aria-hidden /> Frag Lotti
      </p>
      <ul className="mt-1 max-w-[76ch]">
        {questions.map((question) => (
          <li key={question}>
            <Link href={frageLink(question)} prefetch={false} onClick={() => chipMerken(question)}
              className="group flex min-h-11 items-center gap-2 py-1.5 text-[14px] leading-snug text-foreground hover:text-primary">
              <span className="min-w-0 flex-1 break-words">{question}</span>
              <ArrowRight className="h-4 w-4 shrink-0 text-primary transition-transform duration-fluss ease-out-strong group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Content({ content, plain, target }: {
  content: PlanContent;
  /** Einfache Sprache und Fragen; fehlt, wo es keine geprüfte Fassung gibt. */
  plain?: PlanPlain | null;
  /** Der Kernpunkt, zu dem eine Termin-Marke im Zeitband springen will — `n` zählt hoch, damit derselbe Klick zweimal wirkt. */
  target?: { point: number; n: number } | null;
}) {
  const [marked, setMarked] = useState<number | null>(null);
  useEffect(() => {
    if (!target) return;
    setMarked(target.point);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(`plan-point-${target.point}`)
      ?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    const off = window.setTimeout(() => setMarked(null), 2400);
    return () => window.clearTimeout(off);
  }, [target]);
  return (
    <section aria-labelledby="plan-content" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-content">{content.heading}</span></Kicker>
        {content.as_of_label && <p className="font-mono text-meta text-muted-foreground">Stand {content.as_of_label}</p>}
      </div>
      {plain && <Plain plain={plain} />}
      <SharedAsOf.Provider value={!!content.as_of_label}>
        <div className="max-w-[76ch]"><Statement statement={content.purpose} lead /></div>
        <div className="mt-3 space-y-4">
          {content.groups.map((group) => <Group key={group.key} group={group} marked={marked} />)}
        </div>
      </SharedAsOf.Provider>
      <p className="mt-3 max-w-[76ch] text-hinweis text-muted-foreground">{content.note}</p>
      {/* Wer mehr wissen will, fragt das Ratsarchiv — die Fragen hängen an den Kernpunkten darüber. */}
      {plain && plain.questions.length > 0 && <Questions questions={plain.questions} />}
    </section>
  );
}
