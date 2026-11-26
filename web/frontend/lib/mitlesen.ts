/* Mitlesen während der Sitzung (Plan `docs/plan-sitzungsseite-kurs.md`,
   § 4.5, Schritt 5). Was hier steht, rechnet: welche Schritte es gibt, welcher
   gerade dran ist und woher er kommt. Die Seite
   `app/(app)/council/sitzung/mitlesen/` zeichnet nur.

   Ein Schritt ist eine Boje des Kurses: die Formalien zusammen, jeder Punkt
   einzeln, der nichtöffentliche Teil als letzter. */

import { liveItemKeys, liveStateFresh, type LiveState } from "@/lib/live";
import type { SessionCourse } from "@/lib/course";

export interface Step {
  /** Die Nummer, unter der der Schritt geführt wird — bei den Formalien die erste. */
  key: string;
  label: string;
  items: string[];
  title: string;
  stage: number;
  stageName: string;
  closed: boolean;
}

/** Alle Schritte in der Reihenfolge des Kurses. */
export function steps(course: SessionCourse): Step[] {
  const out: Step[] = [];
  course.stages.forEach((st, si) => {
    for (const cell of st.cells) {
      if (st.kind === "closed") {
        out.push({ key: "closed", label: cell.label, items: [], title: st.name, stage: si, stageName: st.name, closed: true });
        continue;
      }
      const first = cell.items[0];
      out.push({
        key: first, label: cell.label, items: cell.items,
        title: cell.title ?? course.items[first]?.short_title ?? first,
        stage: si, stageName: st.name, closed: false,
      });
    }
  });
  return out;
}

export function stepIndexOf(all: Step[], itemNumber: string | null | undefined): number {
  if (!itemNumber) return -1;
  return all.findIndex((s) => s.key === itemNumber || s.items.includes(itemNumber));
}

/** Woher der aktive Schritt kommt (Plan § 4.5, Tabelle). */
export type Source = "self" | "broadcast" | "paused" | "over";

export interface Stored {
  active: string | null;
  /** `false` heißt: Man hat selbst weitergeblättert, die Übertragung führt nicht mehr. */
  follow: boolean;
}

export interface MitlesenState {
  index: number;
  source: Source;
  /** Wo die Übertragung gerade ist (Index), auch wenn man selbst woanders liest. */
  broadcastIndex: number;
  /** Der Satz unter dem Kurs. */
  note: string;
}

/** Der Zustand des Mitlesens.
 *
 *  - Ausschuss (keine Übertragung): Man gibt selbst den Takt vor.
 *  - Rat, `live_state` frisch: Die Seite folgt der Übertragung — bis man
 *    selbst wegblättert; dann pausiert das Folgen und ein Knopf holt zurück.
 *  - Rat, Stand veraltet: wie im Ausschuss; `finished`: Die Sitzung ist vorbei.
 *
 *  Meldet die Übertragung einen Block, gilt dessen LETZTER Punkt als aktiv
 *  (`liveItemKeys` ordnet ihn zu); die Formalien-Boje ist aktiv, sobald einer
 *  ihrer Punkte läuft. */
export function mitlesenState(
  all: Step[], stored: Stored, live: LiveState | null | undefined, now: Date = new Date(),
): MitlesenState {
  const own = Math.max(0, stepIndexOf(all, stored.active));
  if (live?.finished) {
    return { index: own, source: "over", broadcastIndex: -1, note: "Die Sitzung ist vorbei." };
  }
  if (live && liveStateFresh(live, now)) {
    const keys = all.flatMap((s) => s.items.map((n) => n.replace(/^[ÖN]\s+/iu, "").trim()));
    const laufend = [...liveItemKeys(live, keys)];
    const letzter = laufend[laufend.length - 1];
    const bi = letzter ? all.findIndex((s) => s.items.some((n) => n.replace(/^[ÖN]\s+/iu, "").trim() === letzter)) : -1;
    const ago = agoText(live.as_of, now);
    const stand = `Folgt der Übertragung, ${ago}${ago.endsWith(".") ? "" : "."}`;
    if (bi < 0) return { index: own, source: "self", broadcastIndex: -1, note: SELBST };
    if (stored.follow || stored.active == null) {
      return { index: bi, source: "broadcast", broadcastIndex: bi, note: stand };
    }
    return { index: own, source: own === bi ? "broadcast" : "paused", broadcastIndex: bi, note: stand };
  }
  return { index: own, source: "self", broadcastIndex: -1, note: SELBST };
}

export const SELBST = "Ratslotse weiß nicht, wo die Sitzung gerade ist. Du gibst den Takt vor.";

/** „Stand vor 3 Min." — dieselbe Zusage wie `liveAgoText`, als Satzteil. */
export function agoText(asOf: string, now: Date = new Date()): string {
  const min = Math.max(0, Math.round((now.getTime() - new Date(asOf).getTime()) / 60_000));
  return min < 1 ? "Stand gerade eben" : `Stand vor ${min} Min.`;
}

// ---------------------------------------------------------------------------
// Speichern: je Sitzung im Browser, ohne Konto

const key = (ksinr: number) => `ratslotse:mitlesen:${ksinr}`;

export function loadStored(store: Storage | null | undefined, ksinr: number): Stored {
  try {
    const roh = store?.getItem(key(ksinr));
    if (!roh) return { active: null, follow: true };
    const d = JSON.parse(roh) as Partial<Stored>;
    return { active: typeof d.active === "string" ? d.active : null, follow: d.follow !== false };
  } catch {
    return { active: null, follow: true };
  }
}

export function saveStored(store: Storage | null | undefined, ksinr: number, value: Stored): void {
  try {
    store?.setItem(key(ksinr), JSON.stringify(value));
  } catch {
    // Privates Fenster, voller Speicher: Mitlesen geht trotzdem, nur ohne Gedächtnis.
  }
}

/** Ein Schritt weiter oder zurück — und was danach gespeichert wird. Wer selbst
 *  blättert, folgt der Übertragung nicht mehr; wer auf ihren Stand springt,
 *  folgt wieder. */
export function move(all: Step[], state: MitlesenState, to: number): Stored {
  const i = Math.min(all.length - 1, Math.max(0, to));
  return { active: all[i]?.key ?? null, follow: state.broadcastIndex >= 0 && i === state.broadcastIndex };
}
