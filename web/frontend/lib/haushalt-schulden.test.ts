import { describe, expect, it } from "vitest";
import {
  aufteilungen, core_budget, deEuro, groessterSprung, juengsteZinslast,
  ohneAufteilung, punkte,
} from "./haushalt-schulden";

// Die Schulden-Seite behauptet Sätze wie „den größten Sprung gab es 2021".
// Sie werden GERECHNET, nicht beschriftet — damit sie sich mitverändern, wenn
// ein Jahrgang dazukommt. Eine falsche Rechnung erzeugt hier einen Satz, der
// plausibel klingt und nicht stimmt.

const jahr = (year: number, felder: Partial<Record<string, number | null>> = {}) => ({
  year, total: 0, per_capita: null, credit_market: null, special_funds: null,
  public_authorities: null, municipal_enterprises: null, breakdown_rejected: null,
  ...felder,
}) as never;

describe("core_budget — der Kernhaushalt", () => {
  it("summiert die drei Bestandteile", () => {
    expect(core_budget(jahr(2026, { credit_market: 100, special_funds: 20, public_authorities: 5 })))
      .toBe(125);
  });

  it("behandelt fehlende Nebenposten als null Euro", () => {
    expect(core_budget(jahr(2026, { credit_market: 100 }))).toBe(100);
  });

  it("liefert null, wenn der TRAGENDE Posten fehlt", () => {
    // Ohne Kreditmarktschulden ist die Summe keine Null, sondern unbekannt.
    // Eine 0 stünde als Aussage da, die niemand belegen kann.
    expect(core_budget(jahr(2026, { special_funds: 20 }))).toBeNull();
  });
});

describe("aufteilungen", () => {
  it("nimmt nur Jahre, in denen BEIDE Seiten dastehen", () => {
    const reihe = [
      jahr(2024, { credit_market: 100, municipal_enterprises: 50 }),
      jahr(2025, { credit_market: 110 }),                       // Betriebe fehlen
      jahr(2026, { municipal_enterprises: 60 }),                // Kern fehlt
    ];
    expect(aufteilungen(reihe)).toEqual([{ year: 2024, kern: 100, municipal_enterprises: 50 }]);
  });

  it("liefert für eine leere Reihe eine leere Liste", () => {
    expect(aufteilungen([])).toEqual([]);
  });
});

describe("ohneAufteilung", () => {
  it("sammelt die Jahre, in denen die Aufteilung abgelehnt wurde", () => {
    const reihe = [jahr(2024, { breakdown_rejected: 1 }), jahr(2025)];
    expect(ohneAufteilung(reihe).map((z) => z.year)).toEqual([2024]);
  });
});

describe("punkte — zwei Ansichten, zwei Größenordnungen", () => {
  const reihe = [jahr(2025, { total: 337_000_000, per_capita: 1908 }),
                 jahr(2026, { total: 350_000_000, per_capita: 1970 })];

  it("rechnet Absolutbeträge in Millionen", () => {
    // Sonst stünde die eine Reihe bei 337 und die andere bei 0,0019.
    expect(punkte(reihe, "total").map((p) => p.value)).toEqual([337, 350]);
  });

  it("nimmt Pro-Kopf-Beträge in Euro", () => {
    expect(punkte(reihe, "per_capita").map((p) => p.value)).toEqual([1908, 1970]);
  });

  it("behält das Jahr", () => {
    expect(punkte(reihe, "total").map((p) => p.year)).toEqual([2025, 2026]);
  });
});

describe("groessterSprung", () => {
  const p = [
    { year: 2022, value: 100 },
    { year: 2023, value: 130 },   // +30
    { year: 2024, value: 90 },    // -40
    { year: 2025, value: 140 },   // +50
    { year: 2026, value: 138 },   // -2
  ];

  it("findet den größten Anstieg", () => {
    expect(groessterSprung(p, "rauf")).toEqual({ year: 2025, delta: 50 });
  });

  it("findet den größten Rückgang", () => {
    expect(groessterSprung(p, "runter")).toEqual({ year: 2024, delta: -40 });
  });

  it("nennt das Jahr, in dem der Sprung ANKOMMT", () => {
    // Nicht das Jahr davor: „2025 stiegen die Schulden um 50 Mio." ist der
    // Satz, den die Seite baut.
    expect(groessterSprung(p, "rauf")?.year).toBe(2025);
  });

  it("liefert nichts, wenn es in diese Richtung gar keinen Sprung gibt", () => {
    const nurRauf = [{ year: 2024, value: 10 }, { year: 2025, value: 20 }];
    expect(groessterSprung(nurRauf, "runter")).toBeNull();
  });

  it("zählt einen Stillstand für keine Richtung", () => {
    const gleich = [{ year: 2024, value: 10 }, { year: 2025, value: 10 }];
    expect(groessterSprung(gleich, "rauf")).toBeNull();
    expect(groessterSprung(gleich, "runter")).toBeNull();
  });

  it("verträgt zu kurze Reihen", () => {
    expect(groessterSprung([], "rauf")).toBeNull();
    expect(groessterSprung([{ year: 2026, value: 1 }], "rauf")).toBeNull();
  });
});

describe("juengsteZinslast", () => {
  it("nimmt den letzten Eintrag der Reihe", () => {
    const daten = { interest_expense: [{ year: 2025, value: 1 }, { year: 2026, value: 2 }] };
    expect(juengsteZinslast(daten as never)).toEqual({ year: 2026, value: 2 });
  });

  it("liefert null bei leer und fehlend", () => {
    expect(juengsteZinslast({ interest_expense: [] } as never)).toBeNull();
    expect(juengsteZinslast(null)).toBeNull();
  });
});

describe("deEuro", () => {
  it("rundet und gruppiert deutsch", () => {
    expect(deEuro(1908.4)).toBe("1.908");
    expect(deEuro(1908.6)).toBe("1.909");
    expect(deEuro(0)).toBe("0");
  });

  it("zeigt für „kein Wert“ einen Strich — auch bei NaN und Unendlich", () => {
    // NaN entsteht in `punkte()` bei fehlendem Pro-Kopf-Wert; ohne diese
    // Prüfung stünde „NaN" auf der Seite.
    for (const v of [null, undefined, NaN, Infinity]) expect(deEuro(v)).toBe("—");
  });
});
