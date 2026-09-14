import { describe, expect, it } from "vitest";
import { projiziere, ringe, toenung, toenungSpanne, type GeoFlaeche } from "./gebiete";

/** Ein Quadrat um Oldenburg herum, in Grad. */
function quadrat(lon: number, lat: number, kante: number, name: string): GeoFlaeche<{ name: string }> {
  return {
    type: "Feature",
    properties: { name },
    geometry: {
      type: "Polygon",
      coordinates: [[[lon, lat], [lon + kante, lat], [lon + kante, lat + kante], [lon, lat + kante], [lon, lat]]],
    },
  };
}

describe("Flächen projizieren", () => {
  it("legt alle Flächen gemeinsam in die Box und dreht Norden nach oben", () => {
    const { pfade, hoehe } = projiziere([quadrat(8.2, 53.1, 0.1, "unten"), quadrat(8.2, 53.2, 0.1, "oben")], 300, 400);
    expect(pfade.map((p) => p.eigenschaften.name)).toEqual(["unten", "oben"]);
    // Norden oben: Die nördlichere Fläche hat den kleineren y-Schwerpunkt.
    expect(pfade[1].cy).toBeLessThan(pfade[0].cy);
    expect(hoehe).toBeGreaterThan(0);
    expect(hoehe).toBeLessThanOrEqual(400);
  });

  it("zieht die Stadt nicht in die Breite — ein Längengrad ist auf 53° schmaler", () => {
    // Ein Quadrat in GRAD ist auf 53° Nord in Metern deutlich breiter als hoch;
    // gezeichnet muss es schmaler als hoch herauskommen (cos 53° ≈ 0,6).
    const { pfade } = projiziere([quadrat(8.2, 53.1, 0.1, "eins")], 400, 400);
    const zahlen = [...pfade[0].d.matchAll(/[ML]([\d.]+) ([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
    const breite = Math.max(...zahlen.map((p) => p[0])) - Math.min(...zahlen.map((p) => p[0]));
    const hoch = Math.max(...zahlen.map((p) => p[1])) - Math.min(...zahlen.map((p) => p[1]));
    expect(breite / hoch).toBeCloseTo(Math.cos((53.15 * Math.PI) / 180), 1);
  });

  it("kommt mit MultiPolygon und leerer Eingabe zurecht", () => {
    const insel: GeoFlaeche<{ name: string }> = {
      type: "Feature", properties: { name: "zwei Teile" },
      geometry: { type: "MultiPolygon", coordinates: [
        quadrat(8.2, 53.1, 0.05, "a").geometry.coordinates as number[][][],
        quadrat(8.3, 53.1, 0.05, "b").geometry.coordinates as number[][][],
      ] },
    };
    expect(ringe(insel)).toHaveLength(2);
    expect(projiziere([insel], 300, 300).pfade[0].d.split("Z")).toHaveLength(3);
    expect(projiziere([], 300, 300)).toEqual({ pfade: [], hoehe: 300 });
  });
});

describe("Tönung", () => {
  it("gegen null: nichts ist nichts, der Spitzenwert am kräftigsten", () => {
    expect(toenung(0, 10)).toBeNull();
    expect(toenung(null, 10)).toBeNull();
    expect(toenung(5, 0)).toBeNull();
    const halb = toenung(5, 10)!;
    const voll = toenung(10, 10)!;
    expect(halb).toMatch(/^hsl\(var\(--primary\) \/ 0\.\d+\)$/);
    expect(Number(voll.match(/([\d.]+)\)$/)![1])).toBeGreaterThan(Number(halb.match(/([\d.]+)\)$/)![1]));
  });

  it("über eine Spanne: der schwächste bleibt sichtbar, der stärkste ist am kräftigsten", () => {
    const schwach = Number(toenungSpanne(20.5, 20.5, 25.9)!.match(/([\d.]+)\)$/)![1]);
    const stark = Number(toenungSpanne(25.9, 20.5, 25.9)!.match(/([\d.]+)\)$/)![1]);
    expect(schwach).toBeGreaterThan(0.1);      // keine leere Fläche
    expect(stark).toBeGreaterThan(schwach);
    // Ohne Spanne (alle gleich) bekommen alle denselben Ton.
    expect(toenungSpanne(3, 3, 3)).toBe(toenungSpanne(3, 3, 3));
    expect(toenungSpanne(undefined, 0, 1)).toBeNull();
  });
});
