import { describe, expect, it } from "vitest";
import {
  berichteUrls, deStichtag, deStichtagKurz, herkunftVon, stichtageDesJahres,
} from "./haushalt-vollzug";

// Der Haushaltsvollzug zeigt mehrere Stichtage je Jahrgang. Zwei Fallen:
// Ergebnis- und Finanzhaushalt stehen im SELBEN Bericht (die Adresse darf
// also nicht zweimal in der Liste stehen), und ein Stichtag eines anderen
// Jahrgangs gehört nicht dazu.

const stichtag = (budget_year: number, as_of: string) => ({ budget_year, as_of });
const zeile = (budget_year: number, as_of: string, herkunft_id: number | null) =>
  ({ budget_year, as_of, is_total: 1, herkunft_id });

const DATEN = {
  reporting_dates: [
    stichtag(2026, "2026-06-30"),
    stichtag(2026, "2026-09-30"),
    stichtag(2025, "2025-06-30"),
  ],
  totals: [
    zeile(2026, "2026-06-30", 1),
    zeile(2026, "2026-09-30", 2),
    zeile(2025, "2025-06-30", 3),
  ],
  provenance: {
    "1": { url: "https://example.org/bericht-juni.pdf" },
    "2": { url: "https://example.org/bericht-september.pdf" },
    "3": { url: "https://example.org/bericht-2025.pdf" },
  },
} as never;

describe("deStichtag / deStichtagKurz", () => {
  it("schreibt deutsch, mit und ohne Jahr", () => {
    expect(deStichtag("2026-06-30")).toBe("30.06.2026");
    expect(deStichtagKurz("2026-06-30")).toBe("30. Juni");
  });

  it("lässt in der Kurzform die führende Null weg", () => {
    expect(deStichtagKurz("2026-06-01")).toBe("1. Juni");
  });

  it("behält sie in der langen Form — dort steht sie in einer Zahlenreihe", () => {
    expect(deStichtag("2026-06-01")).toBe("01.06.2026");
  });
});

describe("stichtageDesJahres", () => {
  it("nimmt nur die des gefragten Jahrgangs", () => {
    expect(stichtageDesJahres(DATEN, 2026).map((s) => s.as_of))
      .toEqual(["2026-06-30", "2026-09-30"]);
  });

  it("liefert für einen Jahrgang ohne Stichtage nichts", () => {
    expect(stichtageDesJahres(DATEN, 2030)).toEqual([]);
  });
});

describe("berichteUrls", () => {
  it("nennt je Stichtag eine Adresse, in Stichtags-Reihenfolge", () => {
    expect(berichteUrls(DATEN, 2026)).toEqual([
      "https://example.org/bericht-juni.pdf",
      "https://example.org/bericht-september.pdf",
    ]);
  });

  it("führt DIESELBE Adresse nur einmal", () => {
    // Ergebnis- und Finanzhaushalt stehen im selben Bericht. Ohne die
    // Entdoppelung stünde derselbe Link zweimal im Verzeichnis.
    const doppelt = {
      ...DATEN as object,
      provenance: { "1": { url: "https://example.org/eins.pdf" },
                    "2": { url: "https://example.org/eins.pdf" } },
    } as never;
    expect(berichteUrls(doppelt, 2026)).toEqual(["https://example.org/eins.pdf"]);
  });

  it("überspringt Stichtage ohne Beleg, statt eine Lücke zu erfinden", () => {
    const ohne = {
      ...DATEN as object,
      totals: [zeile(2026, "2026-06-30", null), zeile(2026, "2026-09-30", 2)],
    } as never;
    expect(berichteUrls(ohne, 2026)).toEqual(["https://example.org/bericht-september.pdf"]);
  });

  it("mischt die Jahrgänge nicht", () => {
    expect(berichteUrls(DATEN, 2025)).toEqual(["https://example.org/bericht-2025.pdf"]);
  });
});

describe("herkunftVon", () => {
  it("findet über die Zahl", () => {
    expect(herkunftVon(DATEN, 1)).toEqual({ url: "https://example.org/bericht-juni.pdf" });
  });

  it("liefert null für fehlende und unbekannte Kennung", () => {
    expect(herkunftVon(DATEN, null)).toBeNull();
    expect(herkunftVon(DATEN, 999)).toBeNull();
  });
});
