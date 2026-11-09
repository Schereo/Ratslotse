import { describe, expect, it } from "vitest";

import { clock, nextTiming, restLabel, timeline } from "./recherche-zeit";

describe("nextTiming", () => {
  it("nimmt beim Wiederverbinden den frühesten Start", () => {
    // Live: Rahmen bei 10 s Laufzeit, empfangen um 100 000 ms → Start 90 000.
    const live = nextTiming(undefined, 10, 40, 100_000);
    expect(live.start).toBe(90_000);
    // Nachgeliefert: derselbe alte Rahmen, aber erst um 130 000 ms empfangen.
    // Er darf den Job nicht jünger machen.
    const replay = nextTiming(live, 10, 40, 130_000);
    expect(replay.start).toBe(90_000);
  });

  it("behält die letzte Schätzung bei Rahmen ohne Restzeit", () => {
    const a = nextTiming(undefined, 12, 30, 50_000);
    const b = nextTiming(a, 14, null, 52_000);
    expect(b.remaining).toBe(30);
    expect(b.remainingAt).toBe(12);
  });
});

describe("timeline", () => {
  it("zählt die Restzeit zwischen zwei Rahmen herunter", () => {
    const t = nextTiming(undefined, 20, 30, 100_000);
    const jetzt = timeline(t, 110_000);
    expect(jetzt.elapsed).toBe(30);
    expect(jetzt.rest).toBe(20);
    expect(jetzt.percent).toBe(60);
  });

  it("bleibt unter 97 %, auch wenn die Schätzung überzogen ist", () => {
    const t = nextTiming(undefined, 20, 5, 100_000);
    expect(timeline(t, 200_000).percent).toBe(97);
  });

  it("hat ohne Schätzung keinen Balkenwert", () => {
    const t = nextTiming(undefined, 3, null, 10_000);
    expect(timeline(t, 12_000)).toEqual({ elapsed: 5, rest: null, percent: null });
  });
});

describe("restLabel", () => {
  it.each([
    [null, "dauert etwa eine Minute"],
    [70, "noch ~1 Min"],
    [100, "noch ~2 Min"],
    [43, "noch ~45 Sek"],
    [6, "noch ~5 Sek"],
    [2, "gleich fertig"],
    [-10, "gleich fertig"],
    [-25, "dauert länger als sonst"],
  ])("%s → %s", (rest, text) => {
    expect(restLabel(rest)).toBe(text);
  });
});

describe("clock", () => {
  it("schreibt Minuten und Sekunden", () => {
    expect(clock(0)).toBe("0:00");
    expect(clock(42.7)).toBe("0:42");
    expect(clock(95)).toBe("1:35");
  });
});
