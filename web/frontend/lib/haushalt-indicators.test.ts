import { describe, expect, it } from "vitest";
import {
  differenzFormatVon, einheitWort, formatVon, punkteVon, schreibe,
} from "./haushalt-indicators";

// Die Kennzahlen tragen ihre Einheit als Zeichenkette mit. Der Fehler, der
// hier möglich ist, sieht auf der Seite völlig plausibel aus: „3,50 €" statt
// „3,50 %" — dieselbe Zahl, eine ganz andere Aussage.

/** Zwischen Zahl und Einheit steht ein SCHMALES Leerzeichen (U+2009), kein
 *  gewöhnliches. Das ist eine typografische Entscheidung des Baukastens, und
 *  sie wird hier ausdrücklich geprüft: Ein gewöhnliches Leerzeichen sieht im
 *  Test identisch aus („3,50 %" gegen „3,50 %") und fällt beim Lesen des
 *  Diffs niemandem auf. */
const SCHMAL = "\u2009";

describe("schreibe", () => {
  it("hängt die richtige Einheit an", () => {
    expect(schreibe("percent", 3.5)).toBe(`3,50${SCHMAL}%`);
    expect(schreibe("euro", 1234.5)).toBe(`1.234,50${SCHMAL}€`);
    expect(schreibe("count", 42)).toBe("42");
  });

  it("trennt Zahl und Einheit mit dem schmalen Leerzeichen", () => {
    for (const unit of ["percent", "euro"]) {
      expect(schreibe(unit, 1), unit).toContain(SCHMAL);
      expect(schreibe(unit, 1), unit).not.toContain(" ");
    }
  });

  it("hängt an eine Anzahl gar keine Einheit", () => {
    expect(schreibe("count", 42)).not.toContain(SCHMAL);
  });

  it("zählt Personen ohne Nachkommastellen", () => {
    // „1.234,00 Personen" wäre Unsinn.
    expect(schreibe("count", 1234)).toBe("1.234");
  });

  it("behandelt eine unbekannte Einheit wie Euro", () => {
    // Der Rückfall muss eine Einheit ANHÄNGEN: eine nackte Zahl auf einer
    // Haushalts-Seite liest sich als Euro, also steht es besser dran.
    expect(schreibe("gibtesnicht", 5)).toContain("€");
  });

  it("gruppiert deutsch", () => {
    expect(schreibe("euro", 1234567.89)).toBe(`1.234.567,89${SCHMAL}€`);
  });
});

describe("formatVon", () => {
  it("liefert eine Funktion, die dieselbe Einheit anhängt", () => {
    expect(formatVon("percent")(3.5)).toBe(`3,50${SCHMAL}%`);
    expect(formatVon("count")(7)).toBe("7");
  });
});

describe("differenzFormatVon — der Unterschied zwischen % und %-Punkten", () => {
  it("macht aus Prozent PROZENTPUNKTE", () => {
    // Eine Quote steigt von 3 % auf 5 %: Das sind 2 PROZENTPUNKTE, nicht
    // 2 %. Der Unterschied ist der Kern der Aussage.
    expect(differenzFormatVon("percent")(2)).toBe(`2,00${SCHMAL}%-Punkte`);
  });

  it("benutzt dasselbe schmale Leerzeichen wie `schreibe`", () => {
    // Vor 09/2026 stand hier ein GEWÖHNLICHES Leerzeichen — die Zeile durfte
    // damit zwischen Zahl und Einheit umbrechen, was die Hausregel verbietet
    // („Einheit anhängen, nie umbrechen lassen"). Im Diff sieht man den
    // Unterschied nicht; dieser Test schon.
    expect(differenzFormatVon("percent")(2)).toContain(SCHMAL);
    expect(differenzFormatVon("percent")(2)).not.toContain(" ");
  });

  it("lässt Euro und Anzahl unverändert", () => {
    expect(differenzFormatVon("euro")(100)).toBe(`100,00${SCHMAL}€`);
    expect(differenzFormatVon("count")(3)).toBe("3");
  });
});

describe("einheitWort", () => {
  it.each([["percent", "%"], ["count", "Personen"], ["euro", "€"], ["sonst", "€"]])(
    "%s → %s", (unit, wort) => expect(einheitWort(unit)).toBe(wort));
});

describe("punkteVon", () => {
  const daten = {
    series: [
      { indicator: "a", year: 2026, value: 3 },
      { indicator: "b", year: 2025, value: 9 },
      { indicator: "a", year: 2024, value: 1 },
      { indicator: "a", year: 2025, value: 2 },
    ],
  } as never;

  it("nimmt nur die gefragte Kennzahl", () => {
    expect(punkteVon(daten, "a")).toHaveLength(3);
  });

  it("sortiert nach Jahr — die Reihe wird gezeichnet", () => {
    // Unsortiert liefe die Linie im Zickzack rückwärts.
    expect(punkteVon(daten, "a").map((p) => p.year)).toEqual([2024, 2025, 2026]);
  });

  it("liefert für eine unbekannte Kennzahl nichts", () => {
    expect(punkteVon(daten, "gibtesnicht")).toEqual([]);
  });
});
