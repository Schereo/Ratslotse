import { describe, expect, it } from "vitest";
import {
  punkteText,
  rangDeltaText,
  rangPfeil,
  restOb,
  restObText,
  restObTon,
  restSitze,
  restSitzeText,
  restSitzeTon,
  startverteilung,
  summeOb,
  summeSitze,
  tippSegmente,
  uhrzeitKurz,
} from "./tipp";
import type { TippPartei } from "./tipp";

function partei(slug: string, seats_2021: number | null, color = "#123456"): TippPartei {
  return { slug, short: slug, name: slug, color, color_dark: color, seats_2021 } as TippPartei;
}

describe("startverteilung", () => {
  it("summiert exakt auf die Sitzzahl, proportional zu 2021", () => {
    const parteien = [partei("spd", 12), partei("cdu", 12), partei("gruene", 12), partei("linke", 8), partei("volt", 1)];
    const v = startverteilung(parteien, 52);
    expect(summeSitze(v)).toBe(52);
    // Größenordnung bleibt erhalten: die größte 2021er Liste bleibt vorn.
    expect(v.spd).toBeGreaterThanOrEqual(v.linke);
    expect(v.linke).toBeGreaterThanOrEqual(v.volt);
  });

  it("Listen ohne 2021er Sitz starten bei 0", () => {
    const parteien = [partei("spd", 20), partei("neu", null)];
    const v = startverteilung(parteien, 52);
    expect(v.neu).toBe(0);
    expect(summeSitze(v)).toBe(52);
  });

  it("ohne jedes Gewicht bekommt die erste Liste alles — keine Division durch 0", () => {
    const parteien = [partei("a", 0), partei("b", 0)];
    const v = startverteilung(parteien, 52);
    expect(summeSitze(v)).toBe(52);
    expect(v.a).toBe(52);
  });
});

describe("Rest der Sitzverteilung", () => {
  it("Text und Ton an den drei Fällen", () => {
    expect(restSitzeText(0, 52)).toBe("52 von 52 — passt");
    expect(restSitzeTon(0)).toBe("ok");
    expect(restSitzeText(3, 52)).toBe("Noch 3 Sitze");
    expect(restSitzeText(1, 52)).toBe("Noch 1 Sitz");
    expect(restSitzeTon(3)).toBe("warn");
    expect(restSitzeText(-2, 52)).toBe("2 Sitze zu viel");
    expect(restSitzeText(-1, 52)).toBe("1 Sitz zu viel");
  });

  it("restSitze rechnet gegen die Gesamtzahl", () => {
    expect(restSitze({ a: 20, b: 20 }, 52)).toBe(12);
    expect(restSitze({ a: 52 }, 52)).toBe(0);
    expect(restSitze({ a: 60 }, 52)).toBe(-8);
  });
});

describe("tippSegmente", () => {
  const parteien = [partei("spd", 12, "#e3000f"), partei("cdu", 12, "#1a1a1a")];

  it("je Liste mit Sitzen ein Segment, Breite in Prozent der Gesamtzahl", () => {
    const segs = tippSegmente({ spd: 13, cdu: 0 }, parteien, 52);
    expect(segs).toEqual([{ slug: "spd", farbe: "#e3000f", breite: "25%" }]);
  });

  it("deckelt bei Überschreitung — die Leiste läuft nie über den Rahmen", () => {
    const segs = tippSegmente({ spd: 40, cdu: 40 }, parteien, 52);
    const gesamtbreite = segs.reduce((s, x) => s + parseFloat(x.breite), 0);
    expect(gesamtbreite).toBeCloseTo(100, 5);
  });
});

describe("OB-Prozente", () => {
  it("Summe, Rest, Text und Ton", () => {
    expect(summeOb({ a: 30, b: 70 })).toBe(100);
    expect(restOb({ a: 30, b: 70 })).toBe(0);
    expect(restObText(0)).toBe("100,0 % — passt");
    expect(restObTon(0)).toBe("ok");
    expect(restObText(5.5)).toBe("Noch 5,5 %");
    expect(restObText(-2)).toBe("2,0 % zu viel");
    expect(restObTon(3)).toBe("warn");
  });

  it("rundet Fließkomma-Reste auf eine Nachkommastelle", () => {
    expect(restOb({ a: 33.3, b: 33.3, c: 33.3 })).toBeCloseTo(0.1, 5);
  });
});

describe("Rang-Pfeil", () => {
  it("auf/ab/gleich, null ohne Vergleich oder ohne eigenen Rang", () => {
    expect(rangPfeil(2, 5)).toEqual({ richtung: "auf", um: 3 });
    expect(rangPfeil(5, 2)).toEqual({ richtung: "ab", um: 3 });
    expect(rangPfeil(3, 3)).toEqual({ richtung: "gleich", um: 0 });
    expect(rangPfeil(null, 3)).toBeNull();
    expect(rangPfeil(3, null)).toBeNull();
  });

  it("als Satz", () => {
    expect(rangDeltaText({ richtung: "auf", um: 3 })).toBe("3 Plätze vorgerückt");
    expect(rangDeltaText({ richtung: "auf", um: 1 })).toBe("1 Platz vorgerückt");
    expect(rangDeltaText({ richtung: "ab", um: 2 })).toBe("2 Plätze zurückgefallen");
    expect(rangDeltaText({ richtung: "gleich", um: 0 })).toBe("unverändert");
    expect(rangDeltaText(null)).toBe("");
  });
});

describe("Kleinkram", () => {
  it("punkteText mit Singular", () => {
    expect(punkteText(1)).toBe("1 Punkt");
    expect(punkteText(5)).toBe("5 Punkte");
    expect(punkteText(0)).toBe("0 Punkte");
  });

  it("uhrzeitKurz in deutscher Zeit", () => {
    expect(uhrzeitKurz("2026-09-13T18:02:00Z")).toMatch(/^20:02/);
    expect(uhrzeitKurz(null)).toBeNull();
    expect(uhrzeitKurz("kaputt")).toBeNull();
  });
});
