import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";
import {
  TAKT_LIVE_MS,
  TAKT_RUHE_MS,
  abrufTakt,
  ladeFavorit,
  meldungsGewinner,
  speichereFavorit,
  type Meldung,
  type Stichwahl,
} from "./stichwahl";

const m = (zuwachs: Record<string, number>, bezirke = 3): Meldung => ({ at: "2026-09-27T16:40:00Z", bezirke, zuwachs });

describe("meldungsGewinner", () => {
  it("nennt, wer in den neuen Bezirken mehr Stimmen holte", () => {
    expect(meldungsGewinner(m({ prange: 298, rohr: 312 }))).toBe("rohr");
  });
  it("zählt Stimmen, nicht den Anteil: 480 gegen 520 gewinnt der mit 520", () => {
    expect(meldungsGewinner(m({ prange: 520, rohr: 480 }))).toBe("prange");
  });
  it("schweigt bei Gleichstand, ohne Meldung und ohne neue Bezirke", () => {
    expect(meldungsGewinner(m({ prange: 300, rohr: 300 }))).toBeNull();
    expect(meldungsGewinner(null)).toBeNull();
    expect(meldungsGewinner(m({ prange: 10, rohr: 5 }, 0))).toBeNull();
    expect(meldungsGewinner(m({ prange: 0, rohr: 0 }))).toBeNull();
  });
});

describe("abrufTakt", () => {
  const d = (phase: string, dataset = "live") =>
    ({ phase, dataset, election: { polls_close: "2026-09-27T18:00:00+02:00" } }) as unknown as Stichwahl;
  const vorher = new Date("2026-09-27T15:59:00Z");
  const danach = new Date("2026-09-27T16:00:00Z");
  it("fragt ab Wahlschluss alle 15 Sekunden — auch bevor der erste Bezirk da ist", () => {
    expect(abrufTakt(d("before"), danach)).toBe(TAKT_LIVE_MS);
    expect(abrufTakt(d("counting"), danach)).toBe(TAKT_LIVE_MS);
  });
  it("vorher, nach dem Ende und in der Probe jede Minute", () => {
    expect(abrufTakt(d("before"), vorher)).toBe(TAKT_RUHE_MS);
    expect(abrufTakt(d("complete"), danach)).toBe(TAKT_RUHE_MS);
    expect(abrufTakt(d("counting", "probe"), danach)).toBe(TAKT_RUHE_MS);
    expect(abrufTakt(undefined)).toBe(TAKT_RUHE_MS);
  });
});

describe("Favorit", () => {
  let speicher: ReturnType<typeof speicherStub>;
  beforeEach(() => {
    speicher = speicherStub();
    vi.stubGlobal("localStorage", speicher);
  });
  const beide = ["prange", "rohr"];

  it("merkt sich die Wahl je Stichwahl", () => {
    speichereFavorit("ob-stichwahl-2026", "rohr");
    expect(ladeFavorit("ob-stichwahl-2026", beide)).toBe("rohr");
    expect(ladeFavorit("ob-stichwahl-2031", beide)).toBeNull();
  });
  it("vergisst sie mit „niemand“", () => {
    speichereFavorit("ob-stichwahl-2026", "prange");
    speichereFavorit("ob-stichwahl-2026", null);
    expect(ladeFavorit("ob-stichwahl-2026", beide)).toBeNull();
  });
  it("nimmt keinen Namen an, der nicht zur Wahl steht, und kein kaputtes JSON", () => {
    localStorage.setItem("ratslotse:stichwahl-favorit", JSON.stringify({ wahl: "ob-stichwahl-2026", slug: "krogmann" }));
    expect(ladeFavorit("ob-stichwahl-2026", beide)).toBeNull();
    localStorage.setItem("ratslotse:stichwahl-favorit", "{kaputt");
    expect(ladeFavorit("ob-stichwahl-2026", beide)).toBeNull();
  });
  it("übersteht einen gesperrten Speicher (privates Fenster)", () => {
    speicher.kaputt(true);
    expect(() => speichereFavorit("ob-stichwahl-2026", "rohr")).not.toThrow();
    expect(ladeFavorit("ob-stichwahl-2026", beide)).toBeNull();
  });
});
