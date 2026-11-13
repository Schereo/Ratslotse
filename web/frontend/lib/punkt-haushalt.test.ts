import { describe, expect, it } from "vitest";
import { anteil, anteilSatz, haushaltSeite, jahrSpalte, wert } from "./punkt-haushalt";

const nb = (s: string) => s.replace(/\u00a0/g, " ");

describe("wert", () => {
  it("Euro mit passender Einheit und immer mit €", () => {
    expect(nb(wert(65_370_096, "EUR"))).toBe("65,4 Mio. €");
    expect(nb(wert(481_300, "EUR"))).toBe("481 Tsd. €");
    expect(nb(wert(1908, "EUR"))).toBe("1.908 €");
    expect(nb(wert(-10_128_335, "EUR"))).toBe("-10,1 Mio. €");
  });
  it("Sätze in Prozent, Stückzahlen ohne Einheit, Lücken als Strich", () => {
    expect(nb(wert(539, "percent"))).toBe("539 %");
    expect(wert(176_000, "count")).toBe("176.000");
    expect(wert(null, "EUR")).toBe("—");
  });
});

describe("anteil", () => {
  it("rundet genau einmal", () => {
    expect(nb(anteil(0.7994))).toBe("0,8 %");
    expect(nb(anteil(12.6))).toBe("13 %");
  });
  it("unter einem Zehntelprozent keine 0,0", () => {
    expect(nb(anteil(0.0795))).toBe("weniger als 0,1 %");
  });
  it("der ganze Satz", () => {
    expect(nb(anteilSatz({ amount: 481_300, of: 60_208_000, year: 2025, percent: 0.7994 })))
      .toBe("481.300 € sind 0,8 % der geplanten Aufwendungen 2025 dieses Teilhaushalts.");
  });
});

describe("haushaltSeite und jahrSpalte", () => {
  it("kennt nur Seiten, die es gibt", () => {
    expect(haushaltSeite("taxes")).toBe("/haushalt/steuer");
    expect(haushaltSeite("gibt-es-nicht")).toBeNull();
    expect(haushaltSeite(null)).toBeNull();
  });
  it("ein Hebesatz gilt ab dem Jahr", () => {
    expect(jahrSpalte("rate")).toBe("Ab");
    expect(jahrSpalte("plan")).toBe("Jahr");
  });
});
