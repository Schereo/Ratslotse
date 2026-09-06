import { describe, expect, it } from "vitest";
import {
  balken, herkunftVon, indicator, juengstesJahr, steuerkraftJeEinwohner,
} from "./haushalt-vergleich";

// Der Städtevergleich stellt Oldenburg neben andere. Der teure Fehler wäre
// hier keine Ausnahme, sondern eine falsche REIHENFOLGE oder ein falscher
// Nenner: Die Seite behauptet dann eine Rangfolge, die es nicht gibt.

const wert = (key: string, series: string, indicatorName: string, year: number, value: number) =>
  ({ key, series, indicator: indicatorName, year, value, provenance_id: null });

const DATEN = {
  cities: [
    { key: "ol", name: "Oldenburg", is_oldenburg: true, below_100k: false },
    { key: "os", name: "Osnabrück", is_oldenburg: false, below_100k: false },
    { key: "de", name: "Delmenhorst", is_oldenburg: false, below_100k: true },
  ],
  years: { tax_capacity: [2024, 2025, 2026], real_taxes: [2025] },
  values: [
    // Steuerkraftmesszahl in TAUSEND Euro, Einwohner als Zahl.
    wert("ol", "tax_capacity", "steuerkraftmesszahl", 2026, 200_000),
    wert("ol", "tax_capacity", "population", 2026, 175_000),
    wert("os", "tax_capacity", "steuerkraftmesszahl", 2026, 190_000),
    wert("os", "tax_capacity", "population", 2026, 165_000),
    wert("de", "tax_capacity", "steuerkraftmesszahl", 2026, 50_000),
    wert("de", "tax_capacity", "population", 2026, 77_000),
    // ein Jahr daneben, darf nicht mitgerechnet werden
    wert("ol", "tax_capacity", "steuerkraftmesszahl", 2025, 999_999),
  ],
  provenance: { "7": { document: "Statistikbericht" } },
} as never;

describe("indicator", () => {
  it("liefert je Stadt genau den gefragten Jahrgang", () => {
    const m = indicator(DATEN, "tax_capacity", "steuerkraftmesszahl", 2026);
    expect(m.get("ol")?.value).toBe(200_000);
    expect(m.size).toBe(3);
  });

  it("mischt keine Jahrgänge", () => {
    // Der Wert von 2025 steht mit Absicht in den Daten: Ein Vergleich, der
    // Jahre vermischt, sieht plausibel aus und ist falsch.
    expect(indicator(DATEN, "tax_capacity", "steuerkraftmesszahl", 2026).get("ol")?.value)
      .not.toBe(999_999);
  });

  it("liefert nichts für eine unbekannte Kennzahl oder Reihe", () => {
    expect(indicator(DATEN, "tax_capacity", "gibtesnicht", 2026).size).toBe(0);
    expect(indicator(DATEN, "real_taxes", "steuerkraftmesszahl", 2026).size).toBe(0);
  });
});

describe("juengstesJahr", () => {
  it("nimmt das letzte der Reihe", () => {
    expect(juengstesJahr(DATEN, "tax_capacity")).toBe(2026);
    expect(juengstesJahr(DATEN, "real_taxes")).toBe(2025);
  });

  it("liefert null, wo es keine Jahre gibt", () => {
    expect(juengstesJahr({ years: {} } as never, "tax_capacity")).toBeNull();
  });
});

describe("steuerkraftJeEinwohner", () => {
  const b = steuerkraftJeEinwohner(DATEN, 2026);

  it("rechnet die Messzahl von TAUSEND Euro auf Euro je Kopf um", () => {
    // 200.000 Tsd. € auf 175.000 Einwohner = 1.142,86 € — ohne den Faktor
    // 1000 stünden dort 1,14 €.
    expect(b.find((x) => x.key === "ol")!.value).toBeCloseTo(1142.86, 1);
  });

  it("sortiert absteigend — die Rangfolge IST die Aussage", () => {
    expect(b.map((x) => x.key)).toEqual(["os", "ol", "de"]);
    expect(b[0].value).toBeGreaterThan(b[1].value);
  });

  it("reicht die Merkmale der Stadt durch", () => {
    expect(b.find((x) => x.key === "ol")!.ist_oldenburg).toBe(true);
    expect(b.find((x) => x.key === "de")!.unter_100k).toBe(true);
  });

  it("lässt eine Stadt weg, statt durch null zu teilen", () => {
    const ohne = {
      ...DATEN as object,
      values: [wert("x", "tax_capacity", "steuerkraftmesszahl", 2026, 100),
               wert("x", "tax_capacity", "population", 2026, 0)],
      cities: [{ key: "x", name: "X", is_oldenburg: false, below_100k: false }],
    } as never;
    expect(steuerkraftJeEinwohner(ohne, 2026)).toEqual([]);
  });

  it("lässt eine Stadt weg, der eine der beiden Zahlen fehlt", () => {
    expect(steuerkraftJeEinwohner(DATEN, 2025)).toEqual([]);   // nur Messzahl, keine Einwohner
  });
});

describe("balken", () => {
  it("liefert die gespeicherte Kennzahl unverändert", () => {
    const daten = {
      ...DATEN as object,
      values: [wert("ol", "real_taxes", "hebesatz_gewerbe", 2025, 435)],
    } as never;
    expect(balken(daten, "real_taxes", "hebesatz_gewerbe", 2025)[0].value).toBe(435);
  });

  it("lässt Städte ohne Wert weg, statt sie mit 0 zu zeigen", () => {
    // Eine Null wäre eine Aussage („dort ist der Hebesatz null"), die Lücke
    // ist die Wahrheit.
    expect(balken(DATEN, "real_taxes", "hebesatz_gewerbe", 2025)).toEqual([]);
  });
});

describe("herkunftVon", () => {
  it("findet den Beleg über die Zahl", () => {
    expect(herkunftVon(DATEN, 7)).toEqual({ document: "Statistikbericht" });
  });

  it("liefert null für fehlende und unbekannte Kennung", () => {
    expect(herkunftVon(DATEN, null)).toBeNull();
    expect(herkunftVon(DATEN, undefined)).toBeNull();
    expect(herkunftVon(DATEN, 999)).toBeNull();
  });
});
