import { describe, expect, it } from "vitest";
import { KANDIDATUREN, VORGABE, paarSetzen, potenzialPfad, saldoSatz, toenungWert, uebernommenLesen, uebernommenSchreiben } from "./potenzial";
import { speicherStub } from "./__testhilfen/speicher";

describe("potenzialPfad", () => {
  it("trägt bei Vorgaben nur den Token", () => {
    expect(potenzialPfad("abc-123", VORGABE)).toBe("/wahlabend/stichwahl/potenzial?token=abc-123");
  });

  it("nennt nur die Regler, die von der Vorgabe abweichen", () => {
    const r = { ...VORGABE, boldt: { rohr: 70, prange: 10 }, turnoutPrange: 95 };
    const pfad = potenzialPfad("t", r);
    expect(pfad).toContain("boldt=70%2C10");
    expect(pfad).toContain("turnout_prange=95");
    expect(pfad).not.toContain("kuessner=");
    expect(pfad).not.toContain("turnout_rohr=");
  });

  it("rundet auf ganze Prozent — der Server nimmt keine Kommazahlen", () => {
    const r = { ...VORGABE, cdu: { rohr: 33.4, prange: 20.6 } };
    expect(potenzialPfad("t", r)).toContain("cdu=33%2C21");
  });

  it("kennt jede Kandidatur der Vorgabe", () => {
    for (const k of KANDIDATUREN) expect(VORGABE[k.slug]).toBeDefined();
  });
});

describe("paarSetzen", () => {
  it("drückt die andere Seite, wenn die Summe über 100 ginge", () => {
    expect(paarSetzen({ rohr: 55, prange: 15 }, "rohr", 90)).toEqual({ rohr: 90, prange: 10 });
    expect(paarSetzen({ rohr: 55, prange: 15 }, "prange", 60)).toEqual({ rohr: 40, prange: 60 });
  });

  it("lässt die andere Seite in Ruhe, solange Platz ist", () => {
    expect(paarSetzen({ rohr: 55, prange: 15 }, "rohr", 60)).toEqual({ rohr: 60, prange: 15 });
  });

  it("hält sich an 0…100", () => {
    expect(paarSetzen({ rohr: 55, prange: 15 }, "rohr", 130)).toEqual({ rohr: 100, prange: 0 });
    expect(paarSetzen({ rohr: 55, prange: 15 }, "rohr", -5)).toEqual({ rohr: 0, prange: 15 });
  });
});

describe("saldoSatz", () => {
  it("sagt, wer vorn läge, mit Tausenderpunkt", () => {
    expect(saldoSatz(2994)).toBe("Rohr läge 2.994 Stimmen vorn.");
    expect(saldoSatz(-1200)).toBe("Prange läge 1.200 Stimmen vorn.");
    expect(saldoSatz(0)).toContain("Gleichstand");
  });
});

describe("toenungWert", () => {
  const bezirk = {
    eligible: 1000, non_voters: 400, rohr_pct_of_two: 48.2, pool_pct: 30.1, cdu_council: 250, yield_per_1000: 31.5, postal: false,
  };
  it("liest je Modus das passende Feld", () => {
    expect(toenungWert(bezirk, "yield_per_1000")).toBe(31.5);
    expect(toenungWert(bezirk, "rohr_pct_of_two")).toBe(48.2);
    expect(toenungWert(bezirk, "pool_pct")).toBe(30.1);
  });
  it("setzt CDU und Nichtwählende ins Verhältnis zu den Wahlberechtigten", () => {
    expect(toenungWert(bezirk, "cdu_council")).toBe(25);
    expect(toenungWert(bezirk, "non_voters")).toBe(40);
  });
  it("hat für die Briefwahl keinen Wert", () => {
    expect(toenungWert({ ...bezirk, postal: true, yield_per_1000: null }, "yield_per_1000")).toBeNull();
    expect(toenungWert({ ...bezirk, eligible: 0 }, "cdu_council")).toBeNull();
  });
});

describe("übernommen (localStorage)", () => {
  it("merkt sich Bezirksnummern und übersteht einen gesperrten Speicher", () => {
    const s = speicherStub();
    uebernommenSchreiben(s, new Set([109, 501]));
    expect([...uebernommenLesen(s)].sort()).toEqual([109, 501]);
    s.kaputt(true);
    expect(uebernommenLesen(s).size).toBe(0);
    expect(() => uebernommenSchreiben(s, new Set([1]))).not.toThrow();
  });
  it("ignoriert Müll im Speicher", () => {
    const s = speicherStub();
    s.setItem("stichwahl-potenzial-uebernommen", "{nicht json");
    expect(uebernommenLesen(s).size).toBe(0);
  });
});
