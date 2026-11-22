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
  OUTCOME_DOT_CLS, OUTCOME_FILL_CLS, OUTCOME_GLOW_CLS, OUTCOME_RING_CLS, OUTCOME_WORD,
} from "@/components/decision-ui";
import {
  COURSE_MEASURE, courseAriaLabel, courseInput, layoutCourse,
  type Buoy, type CellLayout, type CourseResults, type Density, type Line, type SessionCourse,
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

  // Der Aufbau läuft einmal, beim ersten Zeichnen (globals.css „Der Kurs baut
  // sich auf"). Danach — Umbruch bei anderer Breite, neues Ergebnis beim
  // Mitlesen — steht der Kurs einfach da. Bei reduzierter Bewegung gar nicht:
  // Der globale Block kürzt nur die DAUER, die Verzögerung bliebe, und die
  // Bojen tauchten nacheinander aus dem Nichts auf.
  const zellen = layout?.rows.reduce((n, r) => n + r.cells.length, 0) ?? 0;
  const takt = zellen ? Math.min(55, Math.max(22, 1100 / zellen)) : 0;
  const [bauen, setBauen] = useState<boolean | null>(null);
  useEffect(() => {
    if (!layout || bauen !== null) return;
    const ruhig = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (ruhig) { setBauen(false); return; }
    setBauen(true);
    const t = window.setTimeout(() => setBauen(false), zellen * takt + 700);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout]);
  const aufbau = bauen ? takt : null;
  let start = 0;

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
      {layout?.rows.map((row, r) => {
        const ab = start;
        start += row.cells.length;
        return (
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
          {row.cells.map((cell, c) => {
            // Wo die Karte unter der Boje ansetzt: am Zeilenrand bündig, sonst mittig.
            const sicht = row.reverse ? row.cells.length - 1 - c : c;
            const kante = sicht < 2 ? "start" : sicht > row.cells.length - 3 ? "end" : "mitte";
            return (
              <Cell key={c} cell={cell} reverse={row.reverse} layout={layout} onSelect={onSelect}
                kante={kante} verzug={aufbau == null ? null : (ab + c) * aufbau} />
            );
          })}
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
                ...(aufbau == null ? {} : {
                  animation: `kurs-band var(--takt-fluss) var(--ease-out-strong) ${(ab + row.cells.length) * aufbau}ms both`,
                }),
              }}
            />
          )}
        </div>
        );
      })}
    </div>
  );
}

type Kante = "start" | "mitte" | "end";

function Cell({ cell, reverse, layout, onSelect, kante, verzug }: {
  cell: CellLayout; reverse: boolean; layout: NonNullable<ReturnType<typeof layoutCourse>>;
  onSelect?: (itemNumber: string) => void;
  /** Wo die Hover-Karte ansetzt (in Leserichtung des Bildschirms). */
  kante: Kante;
  /** Aufbau: ab wann diese Zelle dran ist (ms) — `null`: kein Aufbau. */
  verzug: number | null;
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
    // Beim Zeigen hebt sich die ganze Zelle: Die Abschnitts-Beschriftungen
    // (z-[1]) laufen sonst über die Hover-Karte, denn der Aufbau macht die Boje
    // zu einem eigenen Stapel, aus dem ihr z-30 nicht herausreicht.
    <div className="relative flex min-w-0 flex-1 basis-0 flex-col items-center hover:z-20 has-[:focus-visible]:z-20">
      {inBand && (
        <span
          aria-hidden
          className={cn("absolute inset-y-0", cell.closed ? "bg-card/30" : "bg-card/60")}
          style={{
            left, right, borderRadius: `${radL}px ${radR}px ${radR}px ${radL}px`,
            ...(verzug == null ? {} : { animation: `kurs-band var(--takt-buehne) var(--ease-out-strong) ${Math.max(0, verzug - 120)}ms both` }),
          }}
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
            ...(verzug == null ? {} : { animation: `kurs-band var(--takt-buehne) var(--ease-out-strong) ${Math.max(0, verzug - 120)}ms both` }),
          }}
        >
          {cell.label}
        </span>
      )}
      <span
        className="relative flex items-center self-stretch"
        style={{ height: layout.node, marginTop: layout.head, flexDirection: reverse ? "row-reverse" : "row" }}
      >
        {/* Die Linie wächst in Wegrichtung: von links, in rückwärts laufenden
            Zeilen von rechts. */}
        <span aria-hidden className={cn("h-0 flex-1 basis-0 border-t-2", LINE_CLS[cell.lineBefore])}
          style={linie(verzug, -0.6, reverse)} />
        <span className="group/tipp relative flex flex-none"
          style={verzug == null ? undefined : { animation: `kurs-boje var(--takt-buehne) var(--ease-back-out) ${verzug}ms both` }}>
          <Node cell={cell} compact={compact} onSelect={onSelect} />
          <Tipp cell={cell} kante={kante} />
        </span>
        <span aria-hidden className={cn("h-0 flex-1 basis-0 border-t-2", LINE_CLS[cell.lineAfter])}
          style={linie(verzug, 0.25, reverse)} />
      </span>
      {cell.number && (
        <span
          className={cn(
            "relative mt-0.5 whitespace-nowrap font-mono leading-[14px] tracking-[0.05em]",
            cell.numberStrong ? "font-bold text-foreground" : "font-medium text-muted-foreground",
          )}
          style={{
            fontSize: compact ? 9.5 : 10.5,
            ...(verzug == null ? {} : { animation: `kurs-band var(--takt-buehne) var(--ease-out-strong) ${verzug + 80}ms both` }),
          }}
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

/** Ein Linienstück im Aufbau: wächst per `scaleX` aus der Richtung, aus der
 *  der Weg kommt. `versatz` in Takten relativ zur Boje (vorher negativ). */
function linie(verzug: number | null, versatz: number, reverse: boolean): React.CSSProperties | undefined {
  if (verzug == null) return undefined;
  const takt = 45;
  return {
    transformOrigin: reverse ? "right center" : "left center",
    animation: `kurs-linie var(--takt-fluss) var(--ease-out-strong) ${Math.max(0, verzug + versatz * takt)}ms both`,
  };
}

/** Die Hover-Karte einer Boje (Tims Wunsch 11.11.2026): statt des nativen
 *  Tooltips, der erst nach einer Sekunde und im Systemgrau erscheint. Nur
 *  unter dem Zeiger (`maus:`) und beim Tabben — auf dem Telefon führt der Tipp
 *  ohnehin direkt zum Punkt. Die Boje trägt ihren Namen weiter als
 *  `aria-label`; die Karte ist Beiwerk und für Vorleser verborgen. */
function Tipp({ cell, kante }: { cell: CellLayout; kante: Kante }) {
  const b = cell.buoy;
  if (cell.kind === "start") return <TippKarte kante={kante} nummer={cell.number} text="Beginn der Sitzung" />;
  if (!b || cell.kind === "empty" || cell.kind === "pad") return null;
  const vorne = `${b.label} · `;
  const text = b.title.startsWith(vorne) ? b.title.slice(vorne.length) : b.title;
  return <TippKarte kante={kante} nummer={b.label} text={text} buoy={b} />;
}

function TippKarte({ kante, nummer, text, buoy }: { kante: Kante; nummer: string | null; text: string; buoy?: Buoy }) {
  const merkmale: React.ReactNode[] = [];
  if (buoy?.outcome) {
    merkmale.push(
      <span key="e" className="inline-flex items-center gap-1.5">
        <span aria-hidden className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS[buoy.outcome])} />
        {OUTCOME_WORD[buoy.outcome]}{buoy.provisional ? " · vorläufig, aus der Übertragung" : ""}
      </span>,
    );
  }
  if (buoy?.important) merkmale.push(<span key="w">Wichtig</span>);
  if (buoy?.postponed) {
    merkmale.push(
      <span key="v" className="inline-flex items-center gap-1.5">
        <span aria-hidden className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS.postponed)} />
        Stand schon einmal hier und wurde vertagt
      </span>,
    );
  }
  return (
    <span
      aria-hidden
      className={cn(
        "pointer-events-none absolute bottom-full z-30 mb-2 w-max max-w-[min(18rem,80vw)] rounded-xl border border-border bg-popover px-3 py-2 text-left shadow-lg",
        "invisible opacity-0 transition-[opacity,visibility] duration-tipp ease-out-strong",
        "maus:group-hover/tipp:visible maus:group-hover/tipp:opacity-100 group-has-[:focus-visible]/tipp:visible group-has-[:focus-visible]/tipp:opacity-100",
        kante === "start" ? "left-0" : kante === "end" ? "right-0" : "left-1/2 -translate-x-1/2",
      )}
    >
      {nummer && <span className="block font-mono text-[10.5px] font-medium uppercase tracking-[0.06em] text-muted-foreground">{nummer}</span>}
      <span className="mt-0.5 line-clamp-3 block text-[13px] leading-snug text-popover-foreground">{text}</span>
      {merkmale.length > 0 && (
        <span className="mt-1.5 flex flex-col gap-0.5 text-xs text-muted-foreground">{merkmale}</span>
      )}
    </span>
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
        role="img"
        aria-label="Beginn der Sitzung"
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
        role="img"
        aria-label={b.title}
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
    // Unter dem Zeiger hebt sich die Boje ein wenig — nur mit Maus und nur,
    // wo Bewegung erwünscht ist (DESIGNSPRACHE § 5/§ 7).
    "relative box-border flex items-center justify-center rounded-full",
    cell.interactive && "motion-safe:transition-transform motion-safe:duration-tipp maus:group-hover:scale-110",
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
    "group relative flex h-11 w-11 flex-none items-center justify-center rounded-full",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    cell.passed && "opacity-55",
  );
  // Die Trefferfläche ist 44 × 44, die Boje kleiner — der negative Rand hält
  // die Linie trotzdem an der Boje.
  const margin = { marginLeft: -Math.round((44 - size) / 2), marginRight: -Math.round((44 - size) / 2) };
  const label = b.title + (b.postponed ? " · stand schon einmal hier und wurde vertagt" : "");

  if (!cell.interactive) {
    return <span role="img" aria-label={label} className={hit} style={margin}>{inner}</span>;
  }
  if (onSelect) {
    const ziel = b.items[0] ?? b.label;
    return (
      <button
        type="button"
        onClick={() => onSelect(ziel)}
        aria-label={label}
        aria-current={cell.active ? "step" : undefined}
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
      className={hit}
      style={margin}
    >
      {inner}
    </a>
  );
}
