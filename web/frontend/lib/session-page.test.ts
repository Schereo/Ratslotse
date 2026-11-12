import { describe, expect, it } from "vitest";
import {
  dayWord, formalActTitle, groupFormalActs, outcomeCounts, priorStations, sessionKicker,
  sessionPhase, splitNumber,
} from "./session-page";

// Die Tabelle aus Plan § 4.3: vorher, läuft, vorbei ohne Protokoll, vorbei mit.
describe("sessionPhase", () => {
  const ausschuss = { committee: "Verkehrsausschuss", session_time: "17:00", live_until: "20:00" };
  const um = (iso: string) => new Date(iso);

  it("vorher: heute oder später, nicht live", () => {
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21" }, um("2026-09-20T10:00:00"))).toBe("before");
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21" }, um("2026-09-21T16:29:00"))).toBe("before");
  });
  it("läuft: Startzeit erreicht, Ende nicht — 16:29 gegen 17:00", () => {
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21" }, um("2026-09-21T17:00:00"))).toBe("live");
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21" }, um("2026-09-21T19:59:00"))).toBe("live");
  });
  it("vorbei ohne Protokoll und mit", () => {
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21" }, um("2026-09-22T09:00:00"))).toBe("past");
    expect(sessionPhase({ ...ausschuss, session_date: "2026-09-21", has_protocol: true }, um("2026-09-22T09:00:00")))
      .toBe("protocol");
  });
});

describe("Kicker", () => {
  it("nennt Heute und Morgen, sonst den Wochentag", () => {
    const jetzt = new Date("2026-09-20T10:00:00");
    expect(dayWord("2026-09-20", jetzt)).toBe("Heute");
    expect(dayWord("2026-09-21", jetzt)).toBe("Morgen");
    expect(dayWord("2026-09-28", jetzt)).toMatch(/^Montag$/);   // Zusage: der Wochentag, ausgeschrieben
  });
  it("trägt den vollen Ort samt Straße — eine zweite Stelle dafür gibt es nicht", () => {
    expect(sessionKicker({ session_date: "2026-09-21", session_time: "17:00:00",
      location: "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2" }, new Date("2026-09-20T10:00:00")))
      .toBe("Morgen · 21.09.2026 · 17:00 Uhr · Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2");
  });
});

describe("Zählung und Gruppen", () => {
  it("zählt Ergebnisse von Punkten, null entfällt", () => {
    const r = outcomeCounts(["Ö 1", "Ö 5", "Ö 6", "Ö 7", "Ö 15.3"],
      { "5": "noted", "6": "accepted", "7": "accepted", "15.3": "postponed" });
    expect(r).toEqual({ counts: [["accepted", 2], ["noted", 1], ["postponed", 1]], withResult: 4 });
  });
  it("legt nur AUFEINANDERFOLGENDE Formalakte zusammen", () => {
    const formal = new Set(["Ö 5", "Ö 6", "Ö 7", "Ö 10"]);
    expect(groupFormalActs(["Ö 5", "Ö 6", "Ö 7", "Ö 8", "Ö 10"], (n) => formal.has(n)))
      .toEqual([["Ö 5", "Ö 6", "Ö 7"], ["Ö 8"], ["Ö 10"]]);
    expect(formalActTitle(["Widmung der Straße X", "Widmung Y", "Widmung Z"])).toBe("Drei Widmungen");
    expect(formalActTitle(["Widmung X", "Teileinziehung Y"])).toBe("Zwei straßenrechtliche Formalakte");
  });
  it("trennt das Präfix von der Nummer und findet frühere Stationen", () => {
    expect(splitNumber("Ö 11.1")).toEqual({ prefix: "Ö", rest: "11.1" });
    expect(splitNumber("DZT 1")).toEqual({ prefix: "DZT", rest: "1" });
    const weg = [{ ksinr: 1, session_date: "2026-06-03" }, { ksinr: 2, session_date: "2026-06-08" },
      { ksinr: 3, session_date: "2026-06-29" }];
    expect(priorStations(weg, 2, "2026-06-08")).toEqual([weg[0]]);
  });
});
