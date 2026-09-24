import { describe, expect, it } from "vitest";

import { anteil, datumText, jahresmarken, naechster, reihenfolge, satz, spuren, stufe } from "./zeitleiste";

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
    expect(stufe("noted")).toBe("noted");
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

describe("naechster", () => {
  it("findet den Punkt unter dem Zeiger", () => {
    expect(naechster([{ x: 10, y: 5 }, { x: 50, y: 5 }, { x: 90, y: 5 }], 55, 5)).toBe(1);
  });

  it("wiegt die Höhe halb: waagerecht zählt mehr als die Spur", () => {
    // Zeiger bei x=30 auf der Linie. Der Punkt in der Spur darüber liegt
    // 8 px höher, aber nur 2 px daneben — er ist gemeint, nicht der ferne
    // auf der Linie.
    expect(naechster([{ x: 32, y: -3 }, { x: 45, y: 5 }], 30, 5)).toBe(0);
  });

  it("gibt -1 ohne Punkte", () => {
    expect(naechster([], 3, 3)).toBe(-1);
  });
});

describe("reihenfolge", () => {
  it("nach Datum, dann Stadt; ohne Datum ans Ende", () => {
    const p = (city: string, date: string | null) =>
      ({ paper_id: `${city}${date}`, city, date, outcome: "none", kind: "motion" });
    const r = reihenfolge([p("Münster", "2024-02-01"), p("Aachen", null),
                           p("Bonn", "2024-02-01"), p("Kiel", "2023-01-01")]);
    expect(r.map((x) => x.city)).toEqual(["Kiel", "Bonn", "Münster", "Aachen"]);
  });
});

describe("datumText", () => {
  it("deutsch, und sagt, wenn keins da ist", () => {
    expect(datumText("2024-03-12")).toBe("12.03.2024");
    expect(datumText(null)).toBe("ohne Datum");
  });
});
