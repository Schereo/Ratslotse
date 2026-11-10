"use client";

/* „Kurs der Sitzung" — eine Linie vom Anker (Beginn) bis zum Schloss
   (nichtöffentlich), jede Boje ein Punkt, jedes helle Band eine Etappe
   (Plan `docs/plan-sitzungsseite-kurs.md`, § 4.1).

   Diese Komponente misst und zeichnet nur. Was wohin gehört, rechnet
   `lib/course.ts` (mit Tests); was eine Etappe ist und welches Zeichen ein
   Punkt trägt, entscheidet der Server.

   Gedacht für die Anzeigetafel (`.hh-tafel`): Die Bänder sind `--card` mit
   Deckkraft, die Farben kommen aus den Tokens, die die Tafel je Theme neu
   setzt. Kein Literal aus dem Entwurf — sonst ist der Dunkelmodus kaputt. */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  OUTCOME_DOT_CLS, OUTCOME_FILL_CLS, OUTCOME_GLOW_CLS, OUTCOME_RING_CLS,
} from "@/components/decision-ui";
import {
  COURSE_MEASURE, courseAriaLabel, courseInput, layoutCourse,
  type CellLayout, type CourseResults, type Density, type Line, type SessionCourse,
} from "@/lib/course";
import { COURSE_LOCK_ICON, COURSE_START_ICON, courseIcon } from "@/lib/course-icons";
import { cn } from "@/lib/utils";

export interface CourseProps {
  course: SessionCourse;
  results?: CourseResults;
  /** Ziel einer Boje. Ohne `onSelect` ist jede Boje ein Link dorthin
   *  (auf der Sitzungsseite der Anker der Karte, `topDomId`). */
  hrefFor?: (itemNumber: string) => string | undefined;
  /** Mitlesen: Die Boje wählt, statt zu springen. */
  onSelect?: (itemNumber: string) => void;
  active?: string | null;
  density?: Density;
  className?: string;
}

const LINE_CLS: Record<Line, string> = {
  none: "border-transparent",
  normal: "border-primary/30",
  dashed: "border-dashed border-primary/30",
  solid: "border-primary",
};

export function Course({ course, results, hrefFor, onSelect, active, density = "auto", className }: CourseProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // getBoundingClientRect statt clientWidth: Das rundet, und zwar sichtbar
    // auf genau den Breiten, auf denen niemand testet (web/frontend/CLAUDE.md).
    const messen = () => {
      const neu = el.getBoundingClientRect().width;
      setWidth((alt) => (Math.abs(neu - alt) > 1 ? neu : alt));
    };
    messen();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(messen);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const input = useMemo(() => courseInput(course, results, hrefFor), [course, results, hrefFor]);
  const layout = useMemo(
    () => (width > 0 ? layoutCourse(input, width, density, active) : null),
    [input, width, density, active],
  );

  return (
    <div
      ref={ref}
      role="group"
      aria-label={courseAriaLabel(course)}
      className={cn("flex w-full flex-col gap-2", className)}
      // Vor der ersten Messung steht die Höhe einer komfortablen Zeile da,
      // damit die Seite beim Eintreffen nicht springt.
      style={layout ? undefined : { minHeight: 86 }}
    >
      {layout?.rows.map((row, r) => (
        <div
          key={r}
          className="relative flex w-full"
          style={{
            flexDirection: row.reverse ? "row-reverse" : "row",
            height: layout.rowHeight,
            maxWidth: row.maxWidth ?? undefined,
            paddingLeft: COURSE_MEASURE.margin,
            paddingRight: COURSE_MEASURE.margin,
          }}
        >
          {row.cells.map((cell, c) => (
            <Cell key={c} cell={cell} reverse={row.reverse} layout={layout} onSelect={onSelect} />
          ))}
          {row.turn && (
            // Die Kehre: im Rand neben dem Zeilenende, von der Linie dieser
            // Zeile zur Linie der nächsten.
            <span
              aria-hidden
              className={cn(
                "absolute w-[18px] border-2",
                LINE_CLS[row.turn],
                row.reverse ? "left-0 rounded-l-[14px] border-r-0" : "right-0 rounded-r-[14px] border-l-0",
              )}
              style={{
                top: layout.head + layout.node / 2 - 1,
                height: layout.rowHeight + COURSE_MEASURE.rowGap + 2,
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function Cell({ cell, reverse, layout, onSelect }: {
  cell: CellLayout; reverse: boolean; layout: NonNullable<ReturnType<typeof layoutCourse>>;
  onSelect?: (itemNumber: string) => void;
}) {
  const { compact } = layout;
  const inBand = cell.stage >= 0;
  // In Leserichtung: Anfang links, Ende rechts — rückwärts gespiegelt.
  const gapStart = cell.bandStart ? 3 : 0;
  const gapEnd = cell.bandEnd ? 3 : 0;
  const radStart = cell.bandStart ? 12 : 0;
  const radEnd = cell.bandEnd ? 12 : 0;
  const [left, right] = reverse ? [gapEnd, gapStart] : [gapStart, gapEnd];
  const [radL, radR] = reverse ? [radEnd, radStart] : [radStart, radEnd];
  const abzug = compact ? 12 : 20;

  return (
    <div className="relative flex min-w-0 flex-1 basis-0 flex-col items-center">
      {inBand && (
        <span
          aria-hidden
          className={cn("absolute inset-y-0", cell.closed ? "bg-card/30" : "bg-card/60")}
          style={{ left, right, borderRadius: `${radL}px ${radR}px ${radR}px ${radL}px` }}
        />
      )}
      {cell.label && (
        <span
          aria-hidden
          className="absolute top-[5px] z-[1] truncate whitespace-nowrap font-mono font-medium uppercase leading-[14px] tracking-[0.06em] text-muted-foreground"
          style={{
            width: `calc(${Math.max(1, cell.labelCells)} * 100% - ${abzug}px)`,
            fontSize: compact ? 9.5 : 10.5,
            textAlign: reverse ? "right" : "left",
            ...(reverse ? { right: abzug / 2 } : { left: abzug / 2 }),
          }}
        >
          {cell.label}
        </span>
      )}
      <span
        className="relative flex items-center self-stretch"
        style={{ height: layout.node, marginTop: layout.head, flexDirection: reverse ? "row-reverse" : "row" }}
      >
        <span aria-hidden className={cn("h-0 flex-1 basis-0 border-t-2", LINE_CLS[cell.lineBefore])} />
        <Node cell={cell} compact={compact} onSelect={onSelect} />
        <span aria-hidden className={cn("h-0 flex-1 basis-0 border-t-2", LINE_CLS[cell.lineAfter])} />
      </span>
      {cell.number && (
        <span
          className={cn(
            "relative mt-0.5 whitespace-nowrap font-mono leading-[14px] tracking-[0.05em]",
            cell.numberStrong ? "font-bold text-foreground" : "font-medium text-muted-foreground",
          )}
          style={{ fontSize: compact ? 9.5 : 10.5 }}
        >
          {cell.number}
        </span>
      )}
      {cell.showShortTitle && cell.buoy && (
        <span className="relative box-border max-w-full truncate px-1.5 text-center text-xs leading-4 text-foreground">
          {cell.buoy.shortTitle}
        </span>
      )}
    </div>
  );
}

function Node({ cell, compact, onSelect }: {
  cell: CellLayout; compact: boolean; onSelect?: (itemNumber: string) => void;
}) {
  const M = compact ? COURSE_MEASURE.compact : COURSE_MEASURE.comfortable;
  const b = cell.buoy;
  const marker = cell.active ? "outline outline-[3px] outline-offset-2 outline-signal" : "";

  if (cell.kind === "start") {
    return (
      <span
        title="Beginn"
        className="flex flex-none items-center justify-center rounded-full bg-primary text-primary-foreground"
        style={{ width: M.circle, height: M.circle }}
      >
        <COURSE_START_ICON aria-hidden strokeWidth={2.5} style={{ width: M.icon, height: M.icon }} />
      </span>
    );
  }
  if (cell.kind === "lock" && b) {
    return (
      <span
        title={b.title}
        className={cn(
          "flex flex-none items-center justify-center rounded-full border border-dashed border-muted-foreground/55 bg-background text-muted-foreground",
          marker,
        )}
        style={{ width: M.circle, height: M.circle }}
      >
        <COURSE_LOCK_ICON aria-hidden strokeWidth={2} style={{ width: M.icon, height: M.icon }} />
      </span>
    );
  }
  if (!b || cell.kind === "empty" || cell.kind === "pad") return null;

  if (cell.kind === "dot") {
    return (
      <span
        role="img"
        aria-label={b.title}
        title={b.title}
        className={cn(
          "box-border h-2.5 w-2.5 flex-none rounded-full border-2 bg-card",
          b.outcome ? OUTCOME_RING_CLS[b.outcome] : "border-primary/55",
          b.provisional && "border-dashed",
          cell.passed && "opacity-55",
        )}
      />
    );
  }

  const Icon = courseIcon(b.icon);
  const important = cell.kind === "important";
  const size = important ? M.important : M.circle;
  const iconSize = important ? M.importantIcon : M.icon;
  const filled = important && !b.provisional;
  const disc = cn(
    "relative box-border flex items-center justify-center rounded-full",
    important
      ? cn(
          compact ? "ring-[3px]" : "ring-4",
          filled
            ? (b.outcome ? cn(OUTCOME_FILL_CLS[b.outcome], OUTCOME_GLOW_CLS[b.outcome]) : "bg-primary text-primary-foreground ring-primary/15")
            : cn("border-2 border-dashed bg-card text-foreground", b.outcome ? cn(OUTCOME_RING_CLS[b.outcome], OUTCOME_GLOW_CLS[b.outcome]) : "border-primary ring-primary/15"),
        )
      : cn(
          "bg-card text-muted-foreground",
          b.outcome ? cn("border-2", OUTCOME_RING_CLS[b.outcome]) : "border border-primary/35",
          b.provisional && "border-dashed",
        ),
    marker,
  );
  const inner = (
    <span className={disc} style={{ width: size, height: size }}>
      <Icon aria-hidden strokeWidth={2} style={{ width: iconSize, height: iconSize }} />
      {b.postponed && (
        // Der gelbe Punkt: stand schon einmal hier und wurde vertagt. Er
        // trägt die Farbe der Vertagung (OUTCOME_DOT_CLS), umrandet in der
        // Farbe der Fläche, damit er sich von der Boje löst.
        <span
          aria-hidden
          className={cn(
            "absolute -right-0.5 -top-0.5 box-border h-[11px] w-[11px] rounded-full border-2 border-background",
            OUTCOME_DOT_CLS.postponed,
          )}
        />
      )}
    </span>
  );

  const hit = cn(
    "relative flex h-11 w-11 flex-none items-center justify-center rounded-full",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    cell.passed && "opacity-55",
  );
  // Die Trefferfläche ist 44 × 44, die Boje kleiner — der negative Rand hält
  // die Linie trotzdem an der Boje.
  const margin = { marginLeft: -Math.round((44 - size) / 2), marginRight: -Math.round((44 - size) / 2) };
  const label = b.title + (b.postponed ? " · stand schon einmal hier und wurde vertagt" : "");

  if (!cell.interactive) {
    return <span role="img" aria-label={label} title={b.title} className={hit} style={margin}>{inner}</span>;
  }
  if (onSelect) {
    const ziel = b.items[0] ?? b.label;
    return (
      <button
        type="button"
        onClick={() => onSelect(ziel)}
        aria-label={label}
        aria-current={cell.active ? "step" : undefined}
        title={b.title}
        className={hit}
        style={margin}
      >
        {inner}
      </button>
    );
  }
  return (
    <a
      href={b.href ?? "#"}
      aria-label={label}
      aria-current={cell.active ? "step" : undefined}
      title={b.title}
      className={hit}
      style={margin}
    >
      {inner}
    </a>
  );
}
