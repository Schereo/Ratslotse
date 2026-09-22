import { describe, expect, it } from "vitest";

import { anteil, jahresmarken, satz, spuren, stufe } from "./zeitleiste";

const ACHSE = { start: "2023-01-01", end: "2027-01-01" };

describe("anteil", () => {
  it("legt Anfang und Ende auf 0 und 1", () => {
    expect(anteil("2023-01-01", ACHSE)).toBe(0);
    expect(anteil("2027-01-01", ACHSE)).toBe(1);
  });

  it("legt die Mitte in die Mitte", () => {
    expect(anteil("2025-01-01", ACHSE)).toBeCloseTo(0.5, 2);
  });

  it("klemmt, statt zu verwerfen", () => {
    expect(anteil("2021-05-01", ACHSE)).toBe(0);
    expect(anteil("2030-05-01", ACHSE)).toBe(1);
  });

  it("gibt null ohne Datum oder ohne Achse", () => {
    expect(anteil(null, ACHSE)).toBeNull();
    expect(anteil("2024-01-01", { start: null, end: null })).toBeNull();
  });

  it("verträgt eine Achse aus einem einzigen Tag", () => {
    expect(anteil("2024-01-01", { start: "2024-01-01", end: "2024-01-01" })).toBe(0.5);
  });

  it("liest auch ein Datum ohne Tag", () => {
    expect(anteil("2025-01", ACHSE)).toBeCloseTo(0.5, 2);
  });
});

describe("jahresmarken", () => {
  it("setzt je Jahreswechsel eine Marke, Anfang und Ende eingeschlossen", () => {
    expect(jahresmarken(ACHSE).map((m) => m.jahr)).toEqual([2023, 2024, 2025, 2026, 2027]);
    expect(jahresmarken(ACHSE)[0].anteil).toBe(0);
  });

  it("bleibt leer ohne Achse", () => {
    expect(jahresmarken({ start: null, end: null })).toEqual([]);
  });
});

describe("stufe", () => {
  it("fasst acht Ergebnisse zu fünf Stufen", () => {
    expect(stufe("accepted")).toBe("ok");
    expect(stufe("amended")).toBe("ok");
    expect(stufe("rejected")).toBe("no");
    expect(stufe("referred")).toBe("wait");
    expect(stufe("noted")).toBe("neu");
    expect(stufe("withdrawn")).toBe("open");
    expect(stufe(null)).toBe("open");
    expect(stufe("unbekannt")).toBe("open");
  });
});

describe("satz", () => {
  it("liest die Leiste vor", () => {
    const punkte = [
      { paper_id: "1", city: "Osnabrück", date: "2023-06-01", outcome: "accepted", kind: "motion" },
      { paper_id: "2", city: "Münster", date: "2024-02-01", outcome: "accepted", kind: "motion" },
      { paper_id: "3", city: "Potsdam", date: "2026-02-01", outcome: "rejected", kind: "motion" },
      { paper_id: "4", city: "Potsdam", date: null, outcome: "none", kind: "motion" },
    ];
    expect(satz(punkte)).toBe(
      "3 Städte, 2023 bis 2026: zweimal beschlossen, einmal abgelehnt, einmal ohne Ergebnis.");
  });

  it("sagt es, wenn nichts da ist", () => {
    expect(satz([])).toBe("Keine Vorlagen.");
  });

  it("nennt ein einzelnes Jahr nur einmal", () => {
    expect(satz([{ paper_id: "1", city: "A", date: "2024-01-01", outcome: "noted", kind: "x" }]))
      .toBe("1 Stadt, 2024: einmal zur Kenntnis.");
  });
});

describe("spuren", () => {
  it("legt nahe Punkte in Spuren, ohne ihr Datum zu verschieben", () => {
    expect(spuren([0.5, 0.505, 0.51, 0.8])).toEqual([0, 1, -1, 0]);
  });

  it("lässt weit auseinanderliegende Punkte auf der Linie", () => {
    expect(spuren([0.1, 0.5, 0.9])).toEqual([0, 0, 0]);
  });

  it("überlappt in Spur 0, wenn alle Spuren voll sind", () => {
    expect(spuren([0.5, 0.5, 0.5, 0.5])).toEqual([0, 1, -1, 0]);
  });
});
