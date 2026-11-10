/* „Kurs der Sitzung" — die Rechnung (Plan `docs/plan-sitzungsseite-kurs.md`,
   § 4.1 und Anhang C). Eine reine Funktion von (Etappen, Breite, Dichte,
   aktiver Punkt) auf Zeilen und Zellen; die Komponente
   `components/session/course.tsx` misst nur und zeichnet.

   Was eine Etappe ist, welcher Punkt wichtig ist und welches Zeichen er
   trägt, entscheidet der Server (`council/course.py`). Hier wird nur noch
   verteilt: wie viele Bojen in eine Zeile passen, wann der Kurs kompakt
   wird, welcher Etappenname in sein Band passt. Das ist Layout — es hängt an
   der Breite, die nur der Client kennt. */

import type { components } from "@/lib/api-schema";
import type { DecisionOutcome } from "@/lib/types";

export type SessionCourse = components["schemas"]["SessionCourse"];
export type CourseStage = components["schemas"]["CourseStage"];
export type CourseItem = components["schemas"]["CourseItem"];

export type Density = "auto" | "comfortable" | "compact";

/** Eine Boje, so wie der Kurs sie braucht. */
export interface Buoy {
  /** Was unter der Boje steht: „Ö 9", „Ö 1–3". */
  label: string;
  /** Alle Tagesordnungsnummern dieser Boje (die Formalien teilen sich eine). */
  items: string[];
  title: string;
  shortTitle: string;
  icon: string;
  important: boolean;
  postponed: boolean;
  outcome: DecisionOutcome | null;
  /** Ergebnis nur aus der Übertragung, noch ohne Protokoll. */
  provisional: boolean;
  /** Ziel des Links, wenn die Boje einer ist. */
  href?: string;
}

export interface CourseStageInput {
  name: string;
  nameMedium: string | null;
  nameShort: string | null;
  closed: boolean;
  /** Nur am nichtöffentlichen Teil: „N 13–15" und die Zahl der Punkte. */
  closedLabel?: string;
  closedCount?: number;
  buoys: Buoy[];
}

export interface CourseInput {
  start: string | null;
  stages: CourseStageInput[];
}

export type Line = "none" | "normal" | "dashed" | "solid";
export type CellKind = "start" | "buoy" | "important" | "dot" | "lock" | "empty" | "pad";

export interface CellLayout {
  kind: CellKind;
  /** Index der Etappe; -1 für den Start und Füllzellen. */
  stage: number;
  closed: boolean;
  lineBefore: Line;
  lineAfter: Line;
  /** Das helle Band der Etappe beginnt bzw. endet in dieser Zelle (in Leserichtung). */
  bandStart: boolean;
  bandEnd: boolean;
  /** Name der Etappe, wenn er in dieser Zelle beginnt, und über wie viele Zellen er laufen darf. */
  label: string | null;
  labelCells: number;
  /** Nummer unter der Boje (ohne „Ö " im Kompaktmodus) — `null`: keine. */
  number: string | null;
  numberStrong: boolean;
  showShortTitle: boolean;
  active: boolean;
  /** Vor dem aktiven Punkt: Zeichen gedimmt (nur das Zeichen, nie Text). */
  passed: boolean;
  /** Antippbar: komfortabel jede Boje, kompakt nur wichtige und die aktive. */
  interactive: boolean;
  buoy: Buoy | null;
  /** Fortlaufende Position im Kurs (1 = erste Boje), für „Boje 7 von 13". */
  index: number;
}

export interface RowLayout {
  reverse: boolean;
  cells: CellLayout[];
  /** Nur bei einer einzigen Zeile: höchstens so breit (sonst stehen drei Bojen über 1.200 px verteilt). */
  maxWidth: number | null;
  /** Die Kehre zur nächsten Zeile: Linienart wie „nach" der letzten Zelle. */
  turn: Line | null;
}

export interface CourseLayout {
  compact: boolean;
  columns: number;
  cellWidth: number;
  rows: RowLayout[];
  rowHeight: number;
  head: number;
  node: number;
  foot: number;
  /** Zahl der Bojen (Formalien und Schloss je eine) — „Boje 7 von 13". */
  buoyCount: number;
  activeIndex: number;
}

/** Abstände und Größen (Plan § 4.1, „Maße"). */
export const COURSE_MEASURE = {
  margin: 18,
  minComfortable: 60,
  minCompact: 30,
  maxCellSingleRow: 150,
  minShortTitleCell: 104,
  rowGap: 8,
  comfortable: { head: 20, node: 44, foot: 22, footWithShort: 40, circle: 30, important: 40, icon: 15, importantIcon: 18, glow: 4 },
  compact: { head: 18, node: 30, foot: 18, circle: 22, important: 26, icon: 12, importantIcon: 14, glow: 3, dot: 10 },
  /** Mono 10,5 px in Versalien: Schätzung je Zeichen (Entwurf; IBM Plex Mono
   *  misst 0,6 em + 0,06 em Laufweite ≈ 6,9 px — 7,1 lässt etwas Luft). */
  charWidth: 7.1,
} as const;

interface FlatCell {
  kind: "start" | "buoy" | "important" | "lock" | "empty";
  stage: number;
  buoy: Buoy | null;
  stageName: string;
  stageMedium: string | null;
  stageShort: string | null;
  stageCount: number;
  closed: boolean;
}

/** Welche Zelle trägt den aktiven Punkt? Die Formalien-Boje ist aktiv, sobald
 *  einer ihrer Punkte läuft. */
function findActive(cells: FlatCell[], active: string | null | undefined): number {
  if (!active) return -1;
  return cells.findIndex((c) => !!c.buoy && (c.buoy.label === active || c.buoy.items.includes(active)));
}

function flatten(input: CourseInput): FlatCell[] {
  const cells: FlatCell[] = [{
    kind: "start", stage: -1, buoy: null, stageName: "", stageMedium: null, stageShort: null,
    stageCount: 0, closed: false,
  }];
  input.stages.forEach((st, si) => {
    const own: FlatCell[] = st.closed
      ? [{
          kind: "lock", stage: si,
          buoy: {
            label: st.closedLabel ?? "", items: [], title: st.name, shortTitle: st.closedCount
              ? `${st.closedCount} ${st.closedCount === 1 ? "Punkt" : "Punkte"}` : st.name,
            icon: "lock", important: false, postponed: false, outcome: null, provisional: false,
          },
          stageName: st.name, stageMedium: st.nameMedium, stageShort: st.nameShort, stageCount: 1, closed: true,
        }]
      : st.buoys.map((b) => ({
          kind: b.important ? "important" as const : "buoy" as const, stage: si, buoy: b,
          stageName: st.name, stageMedium: st.nameMedium, stageShort: st.nameShort,
          stageCount: st.buoys.length, closed: false,
        }));
    if (own.length === 0) return;
    // Eine Etappe mit nur einer Zelle bekommt eine Leerzelle dazu, damit ihr
    // Name Platz hat — bei der letzten davor, sonst dahinter.
    if (own.length < 2) {
      const empty: FlatCell = { ...own[0], kind: "empty", buoy: null };
      if (si === input.stages.length - 1) own.unshift(empty);
      else own.push(empty);
    }
    cells.push(...own);
  });
  return cells;
}

/** Passt ein Etikett in `space` Pixel? */
const fits = (text: string, space: number) => text.length * COURSE_MEASURE.charWidth <= space;

/** Der Etappenname, der in den Platz passt: voller Name mit Anzahl, dann
 *  Name, dann mittlere, dann knappste Form. Kompakt gibt es nur die knappste. */
export function stageLabel(
  name: string, medium: string | null, short: string | null, count: number,
  space: number, compact: boolean,
): string {
  if (compact) return short ?? "";
  const full = count > 1 ? `${name} · ${count}` : name;
  if (fits(full, space)) return full;
  if (fits(name, space)) return name;
  if (medium && fits(medium, space)) return medium;
  return short ?? medium ?? name;
}

/** Die ganze Rechnung (Anhang C). */
export function layoutCourse(
  input: CourseInput, width: number, density: Density = "auto", active?: string | null,
): CourseLayout {
  const M = COURSE_MEASURE;
  const cells = flatten(input);
  const n = cells.length;
  let lastPublic = 0;
  cells.forEach((c, i) => { if (c.kind === "buoy" || c.kind === "important") lastPublic = i; });
  const activeIndex = findActive(cells, active);

  const usable = Math.max(120, width - 2 * M.margin);
  const fitCols = (min: number) => Math.max(3, Math.floor(usable / min));
  let columns = fitCols(M.minComfortable);
  const compact = density === "compact" || (density === "auto" && Math.ceil(n / columns) > 2);
  if (compact) columns = fitCols(M.minCompact);
  const rowsCount = Math.max(1, Math.ceil(n / columns));
  columns = Math.ceil(n / rowsCount);
  const cellWidth = usable / columns;
  const showShort = !compact && rowsCount === 1 && cellWidth >= M.minShortTitleCell;
  const size = compact ? M.compact : M.comfortable;
  const head = size.head;
  const node = size.node;
  const foot = compact ? M.compact.foot : (showShort ? M.comfortable.footWithShort : M.comfortable.foot);

  // Etappenname: am ersten Stück der Etappe, das in einer Zeile mindestens
  // zwei Zellen hat, sonst am ersten Stück.
  const labelAt = new Map<number, number>();
  const stages = new Set(cells.map((c) => c.stage).filter((s) => s >= 0));
  for (const si of stages) {
    const parts: { row: number; first: number; length: number }[] = [];
    cells.forEach((c, i) => {
      if (c.stage !== si) return;
      const row = Math.floor(i / columns);
      const last = parts[parts.length - 1];
      if (last && last.row === row) last.length += 1;
      else parts.push({ row, first: i, length: 1 });
    });
    if (!parts.length) continue;
    const pick = parts.find((p) => p.length >= 2) ?? parts[0];
    labelAt.set(pick.first, pick.length);
  }

  let buoyIndex = 0;
  const laid: CellLayout[] = cells.map((c, i) => {
    const prev = i > 0 ? cells[i - 1] : null;
    const next = i < n - 1 ? cells[i + 1] : null;
    const isActive = i === activeIndex;
    const lineBefore: Line = i === 0 ? "none"
      : activeIndex >= 0 && i <= activeIndex ? "solid"
      : i > lastPublic ? "dashed" : "normal";
    const lineAfter: Line = i === n - 1 ? "none"
      : activeIndex >= 0 && i < activeIndex ? "solid"
      : i >= lastPublic ? "dashed" : "normal";
    const labelCells = labelAt.get(i) ?? 0;
    const abzug = compact ? 12 : 20;
    const label = labelCells > 0 && c.stage >= 0
      ? stageLabel(c.stageName, c.stageMedium, c.stageShort, c.stageCount,
          Math.max(1, labelCells) * cellWidth - abzug, compact) || null
      : null;
    const stageBegins = !prev || prev.stage !== c.stage;
    const kind: CellKind = c.kind === "buoy" && compact && !isActive ? "dot" : c.kind;
    const strong = c.kind === "important" || c.kind === "start" || isActive;
    const showNumber = c.kind !== "empty"
      && (!compact || c.kind !== "buoy" || stageBegins || isActive);
    const rawNumber = c.kind === "start" ? (input.start ?? "") : (c.buoy?.label ?? "");
    const number = showNumber && rawNumber
      ? (compact ? rawNumber.replace(/^Ö\s+/, "") : rawNumber)
      : null;
    const counts = c.kind === "buoy" || c.kind === "important" || c.kind === "lock";
    if (counts) buoyIndex += 1;
    return {
      kind,
      stage: c.stage,
      closed: c.closed,
      lineBefore,
      lineAfter,
      bandStart: c.stage >= 0 && stageBegins,
      bandEnd: c.stage >= 0 && (!next || next.stage !== c.stage),
      label,
      labelCells,
      number,
      numberStrong: strong,
      showShortTitle: showShort && c.kind !== "empty" && c.kind !== "start",
      active: isActive,
      passed: activeIndex >= 0 && i < activeIndex,
      interactive: (c.kind === "buoy" || c.kind === "important") && (!compact || c.kind === "important" || isActive),
      buoy: c.buoy,
      index: counts ? buoyIndex : 0,
    };
  });

  const rows: RowLayout[] = [];
  for (let r = 0; r < rowsCount; r++) {
    const piece = laid.slice(r * columns, (r + 1) * columns);
    const end = piece[piece.length - 1];
    while (piece.length < columns) {
      piece.push({
        kind: "pad", stage: -1, closed: false, lineBefore: "none", lineAfter: "none",
        bandStart: false, bandEnd: false, label: null, labelCells: 0, number: null,
        numberStrong: false, showShortTitle: false, active: false, passed: false,
        interactive: false, buoy: null, index: 0,
      });
    }
    rows.push({
      reverse: r % 2 === 1,
      cells: piece,
      maxWidth: rowsCount === 1 ? columns * M.maxCellSingleRow + 2 * M.margin : null,
      turn: r < rowsCount - 1 ? (end?.lineAfter ?? "normal") : null,
    });
  }

  return {
    compact, columns, cellWidth, rows, rowHeight: head + node + foot, head, node, foot,
    buoyCount: buoyIndex,
    activeIndex: activeIndex >= 0 ? laid[activeIndex].index : 0,
  };
}

// ---------------------------------------------------------------------------
// Vom Vertrag zur Eingabe

export interface CourseResults {
  /** Ergebnis je Tagesordnungsnummer ohne Präfix („9", „15.1") — aus dem Protokoll. */
  outcomeByItem?: Record<string, DecisionOutcome | null>;
  /** Vorläufiges Ergebnis aus der Übertragung, wo das Protokoll fehlt. */
  provisionalByItem?: Record<string, DecisionOutcome | null>;
}

const OUTCOME_WORD: Record<DecisionOutcome, string> = {
  accepted: "Angenommen", rejected: "Abgelehnt", postponed: "Vertagt",
  noted: "Zur Kenntnis", no_decision: "Kein Beschluss", settled: "Gilt als behandelt",
};

/** „Ö 9" → „9" (wie `topKey` in `components/tagesordnung.tsx`). */
const plainNumber = (n: string) => n.replace(/^\p{L}+\s+/u, "").trim();

/** `course` aus der Sitzungsantwort plus Ergebnisse → Eingabe der Rechnung.
 *  `hrefFor` baut das Ziel einer Boje (Anker der Karte oder Punkt-Seite). */
export function courseInput(
  course: SessionCourse, results: CourseResults = {}, hrefFor?: (itemNumber: string) => string | undefined,
): CourseInput {
  const outcomes = results.outcomeByItem ?? {};
  const provisional = results.provisionalByItem ?? {};
  return {
    start: course.start ?? null,
    stages: course.stages.map((st) => {
      if (st.kind === "closed") {
        return {
          name: st.name, nameMedium: st.name_medium ?? null, nameShort: st.name_short ?? null,
          closed: true, closedLabel: st.cells[0]?.label ?? st.range, closedCount: st.count, buoys: [],
        };
      }
      return {
        name: st.name, nameMedium: st.name_medium ?? null, nameShort: st.name_short ?? null, closed: false,
        buoys: st.cells.map((cell) => {
          const first = cell.items[0];
          const item: CourseItem | undefined = course.items[first];
          const formal = !!cell.title;
          const key = plainNumber(first);
          const outcome = formal ? null : (outcomes[key] ?? null);
          const prov = formal || outcome ? null : (provisional[key] ?? null);
          const shown = outcome ?? prov;
          const name = formal ? cell.title! : (item?.short_title ?? first);
          return {
            label: cell.label,
            items: cell.items,
            title: `${cell.label} · ${name}${shown ? ` · ${OUTCOME_WORD[shown]}${prov ? " (vorläufig)" : ""}` : ""}`,
            shortTitle: name,
            icon: item?.icon ?? "statute",
            important: !formal && !!item?.important,
            postponed: !formal && (item?.postponed ?? 0) > 0,
            outcome: shown,
            provisional: !!prov,
            href: hrefFor?.(first),
          };
        }),
      };
    }),
  };
}

/** „Kurs der Sitzung, 17 Punkte in 5 Etappen" — die Beschriftung des Bausteins. */
export function courseAriaLabel(course: SessionCourse): string {
  const etappen = course.stages.length;
  const punkte = course.public_count;
  return `Kurs der Sitzung, ${punkte} öffentliche ${punkte === 1 ? "Punkt" : "Punkte"} in ${etappen} ${etappen === 1 ? "Etappe" : "Etappen"}`;
}
