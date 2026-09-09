import { describe, expect, it } from "vitest";
import { listenSortiert, prozent, toenungNachStaerke, wahlFlaechen, type Wahlstand } from "./wahl-flaechen";

// Die Ebene „Wahlergebnis": Was hier zählt, ist die Zuordnung Ortsbereich →
// Wahlbereich (der ERSTE gilt für die Fläche) und dass die Tönung mit der
// Stärke wächst, ohne dass eine Parteifarbe je die Fläche bestimmt.

const stand = {
  parties: [
    { slug: "spd", short: "SPD", name: "SPD", color: "#e3000f", color_dark: "#ff4d57" },
    { slug: "gruene", short: "Grüne", name: "Bündnis 90/Die Grünen", color: "#46962b", color_dark: "#6fcb4c" },
  ],
  areas: [
    { number: 1, roman: "I", name: "Stadtmitte Nord", districts_counted: 3, districts_total: 22,
      parties: [{ slug: "spd", share_pct: 24.6, seats: 3 }, { slug: "gruene", share_pct: 37.6, seats: 5 }] },
    { number: 2, roman: "II", name: "Stadtmitte Süd", districts_counted: 0, districts_total: 21,
      parties: [{ slug: "spd", share_pct: null, seats: null }, { slug: "gruene", share_pct: null, seats: null }] },
  ],
} as unknown as Wahlstand;

describe("wahlFlaechen", () => {
  it("legt das Ergebnis des ersten Wahlbereichs auf den Ortsbereich", () => {
    const m = wahlFlaechen(stand, [
      { name: "Nadorst", electoral_districts: [1] },
      { name: "Grenzland", electoral_districts: [2, 1] },
      { name: "Ohne", electoral_districts: [] },
    ]);
    expect(m.get("Nadorst")?.roman).toBe("I");
    expect(m.get("Grenzland")?.roman).toBe("II");
    expect(m.has("Ohne")).toBe(false);
  });
  it("sortiert die Listen nach Anteil, stärkste zuerst, mit Stammdaten aus der Stadtliste", () => {
    const f = wahlFlaechen(stand, [{ name: "Nadorst", electoral_districts: [1] }]).get("Nadorst")!;
    expect(f.listen.map((l) => l.short)).toEqual(["Grüne", "SPD"]);
    expect(f.listen[0].color).toBe("#46962b");
    expect(f.staerke).toBeCloseTo(0.376);
  });
  it("hat vor der Auszählung keine Stärke", () => {
    const f = wahlFlaechen(stand, [{ name: "Süd", electoral_districts: [2] }]).get("Süd")!;
    expect(f.staerke).toBe(0);
    expect(f.counted).toBe(0);
  });
});

describe("Tönung und Anzeige", () => {
  it("wächst mit der Stärke und bleibt zwischen blass und satt", () => {
    expect(toenungNachStaerke(0)).toBeLessThan(toenungNachStaerke(0.25));
    expect(toenungNachStaerke(0.25)).toBeLessThan(toenungNachStaerke(0.45));
    expect(toenungNachStaerke(0.9)).toBe(toenungNachStaerke(0.5));
    expect(toenungNachStaerke(0.5)).toBeLessThanOrEqual(0.65);
  });
  it("schreibt Prozent deutsch und den Gedankenstrich, wo nichts ist", () => {
    expect(prozent(37.56)).toBe("37,6 %");
    expect(prozent(null)).toBe("–");
  });
  it("kennt eine Liste ohne Stammdaten trotzdem", () => {
    expect(listenSortiert([], [{ slug: "x", share_pct: 1, seats: 0 }])[0].short).toBe("x");
  });
});
