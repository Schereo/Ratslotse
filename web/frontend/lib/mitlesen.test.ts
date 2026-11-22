import { describe, expect, it } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";
import { SELBST, loadStored, mitlesenState, move, saveStored, stepIndexOf, steps } from "./mitlesen";
import type { SessionCourse } from "./course";
import type { LiveState } from "./live";

// Jede Zeile der Tabelle aus Plan § 4.5 hat hier einen Fall.

const KURS = {
  start: "18:00", public_count: 8, closed_count: 2, substantive_count: 4, summary: null, summary_source: "rule", next_session: null,
  stages: [
    { kind: "start", name: "Zum Start", name_medium: null, name_short: "Start", subtitle: null, range: "Ö 1 – Ö 4", count: 4,
      cells: [{ label: "Ö 1–3", title: "Formalien", items: ["Ö 1", "Ö 2", "Ö 3"] }, { label: "Ö 4", title: null, items: ["Ö 4"] }] },
    { kind: "content", name: "Beschlüsse und Berichte", name_medium: null, name_short: "Beschlüsse", subtitle: null, range: "Ö 5 – Ö 8", count: 4,
      cells: ["Ö 5", "Ö 6", "Ö 7", "Ö 8"].map((n) => ({ label: n, title: null, items: [n] })) },
    { kind: "closed", name: "Nichtöffentlicher Teil", name_medium: "Nichtöffentlich", name_short: null, subtitle: null, range: "N 9 – N 10", count: 2,
      cells: [{ label: "N 9–10", title: null, items: [] }] },
  ],
  items: Object.fromEntries(["Ö 1", "Ö 2", "Ö 3", "Ö 4", "Ö 5", "Ö 6", "Ö 7", "Ö 8"].map((n) => [n, { short_title: `T${n}` }])),
} as unknown as SessionCourse;

const ALLE = steps(KURS);
const live = (extra: Partial<LiveState>): LiveState => ({
  item_number: "6", item_title: null, block_start: null, phase: null, speaker: null, party: null,
  since: null, as_of: "2026-09-03T18:30:00+02:00", finished: false, ...extra,
} as LiveState);

describe("Schritte", () => {
  it("sind die Bojen: Formalien zusammen, Nichtöffentliches als letzter", () => {
    expect(ALLE.map((s) => s.label)).toEqual(["Ö 1–3", "Ö 4", "Ö 5", "Ö 6", "Ö 7", "Ö 8", "N 9–10"]);
    expect(ALLE[0].title).toBe("Formalien");
    expect(ALLE[6].closed).toBe(true);
    expect(stepIndexOf(ALLE, "Ö 2")).toBe(0);
  });
});

describe("mitlesenState — Plan § 4.5", () => {
  const jetzt = new Date("2026-09-03T18:35:00+02:00");

  it("Ausschuss: man klickt selbst", () => {
    const s = mitlesenState(ALLE, { active: "Ö 5", follow: true }, null, jetzt);
    expect(s).toMatchObject({ index: 2, source: "self", note: SELBST });
  });

  it("Rat, frischer Stand: folgt der Übertragung", () => {
    const s = mitlesenState(ALLE, { active: null, follow: true }, live({}), jetzt);
    expect(s).toMatchObject({ index: 3, source: "broadcast", broadcastIndex: 3 });
    expect(s.note).toBe("Folgt der Übertragung, Stand vor 5 Min.");
  });

  it("Rat, selbst weggeblättert: pausiert, die Übertragung bleibt bekannt", () => {
    const s = mitlesenState(ALLE, { active: "Ö 8", follow: false }, live({}), jetzt);
    expect(s).toMatchObject({ index: 5, source: "paused", broadcastIndex: 3 });
  });

  it("Rat, Stand veraltet: wie im Ausschuss — 20 Minuten sind die Grenze", () => {
    const grenze = new Date("2026-09-03T18:50:00+02:00");
    const danach = new Date("2026-09-03T18:51:00+02:00");
    expect(mitlesenState(ALLE, { active: "Ö 5", follow: true }, live({}), grenze).source).toBe("broadcast");
    expect(mitlesenState(ALLE, { active: "Ö 5", follow: true }, live({}), danach)).toMatchObject({ source: "self", index: 2 });
  });

  it("Rat, beendet: Die Sitzung ist vorbei", () => {
    const s = mitlesenState(ALLE, { active: "Ö 7", follow: true }, live({ finished: true }), jetzt);
    expect(s).toMatchObject({ source: "over", index: 4, note: "Die Sitzung ist vorbei." });
  });

  it("ein Block: sein letzter Punkt ist aktiv; die Formalien, sobald einer läuft", () => {
    expect(mitlesenState(ALLE, { active: null, follow: true }, live({ block_start: "5", item_number: "7" }), jetzt).index).toBe(4);
    expect(mitlesenState(ALLE, { active: null, follow: true }, live({ item_number: "2" }), jetzt).index).toBe(0);
  });

  it("16:29 gegen 16:30 — „Stand gerade eben“ und „vor 1 Min.“", () => {
    const s1 = mitlesenState(ALLE, { active: null, follow: true }, live({ as_of: "2026-09-03T16:29:40+02:00" }), new Date("2026-09-03T16:29:59+02:00"));
    const s2 = mitlesenState(ALLE, { active: null, follow: true }, live({ as_of: "2026-09-03T16:29:00+02:00" }), new Date("2026-09-03T16:30:00+02:00"));
    expect(s1.note).toBe("Folgt der Übertragung, Stand gerade eben.");
    expect(s2.note).toBe("Folgt der Übertragung, Stand vor 1 Min.");
  });
});

describe("Blättern und Speichern", () => {
  it("wer selbst blättert, folgt nicht mehr — wer auf den Stand springt, wieder", () => {
    const s = mitlesenState(ALLE, { active: null, follow: true }, live({}), new Date("2026-09-03T18:35:00+02:00"));
    expect(move(ALLE, s, 4)).toEqual({ active: "Ö 7", follow: false });
    expect(move(ALLE, s, 3)).toEqual({ active: "Ö 6", follow: true });
    expect(move(ALLE, s, 99)).toEqual({ active: "closed", follow: false });
  });

  it("merkt sich den Schritt je Sitzung, auch im gesperrten Speicher ohne Fehler", () => {
    const speicher = speicherStub();
    expect(loadStored(speicher, 1)).toEqual({ active: null, follow: true });
    saveStored(speicher, 1, { active: "Ö 6", follow: false });
    expect(loadStored(speicher, 1)).toEqual({ active: "Ö 6", follow: false });
    expect(loadStored(speicher, 2)).toEqual({ active: null, follow: true });
    speicher.kaputt(true);
    expect(() => saveStored(speicher, 1, { active: "Ö 7", follow: true })).not.toThrow();
    expect(loadStored(speicher, 1)).toEqual({ active: null, follow: true });
  });
});

describe("Lottis Satz im Kopf", () => {
  it("je Zustand ein fester Satz", async () => {
    const { greeting } = await import("./mitlesen");
    expect(greeting("self")).toMatch(/^Tipp auf „Weiter“/);
    expect(greeting("broadcast")).toMatch(/Übertragung/);
    expect(greeting("paused")).toMatch(/Zur Übertragung/);
    expect(greeting("over")).toMatch(/vorbei/);
  });
});
