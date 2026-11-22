import { describe, expect, it } from "vitest";
import {
  byField, byPackage, committeeList, filterMeasures, formatAmount, formatChange, formatDate, percent, reportCount,
  signed, squareTokens, stationKind,
  statusLabels, statusLine, statusSummary, statusTone, yearSpan,
  type PlanCard, type PlanMeasureField,
} from "./plans";

describe("formatDate", () => {
  it("dreht ISO-Daten ohne Zeitzone um", () => {
    expect(formatDate("2022-12-19")).toBe("19.12.2022");
    expect(formatDate("2029-09")).toBe("09/2029");
    expect(formatDate("2035")).toBe("2035");
  });
});

describe("stationKind", () => {
  it("nennt mündliche Berichte als solche", () => {
    expect(stationKind({ kind: "report", oral: true })).toBe("Mündlicher Bericht, ohne Text");
    expect(stationKind({ kind: "report", oral: false })).toBe("Bericht");
    expect(stationKind({ kind: "adoption", oral: false })).toBe("Beschluss des Plans");
  });
});

describe("committeeList", () => {
  it("stellt den Rat ans Ende", () => {
    expect(committeeList(["Rat", "Sozialausschuss"])).toBe("Sozialausschuss · Rat");
    expect(committeeList(["Jugendhilfeausschuss"])).toBe("Jugendhilfeausschuss");
  });
});

describe("statusTone", () => {
  it("kennt keinen Fehler-Ton", () => {
    expect(statusTone("expired")).toBe("neutral");
    expect(statusTone("superseded")).toBe("neutral");
    expect(statusTone("preparing")).toBe("primary");
    expect(statusTone("running")).toBe("none");
  });
});

describe("percent", () => {
  it("macht aus einer Lage auf der Achse eine CSS-Länge", () => {
    expect(percent(0.4661)).toBe("46.61%");
    expect(percent(0)).toBe("0%");
    expect(percent(1)).toBe("100%");
  });
  it("bleibt auf der Achse", () => {
    // Ein Band, dessen Ende vor seinem Beginn läge, bekäme sonst eine negative Breite.
    expect(percent(-0.2)).toBe("0%");
    expect(percent(1.3)).toBe("100%");
  });
});

describe("reportCount und yearSpan", () => {
  it("beugt die Einzahl", () => {
    expect(reportCount(1)).toBe("1 Bericht");
    expect(reportCount(12)).toBe("12 Berichte");
  });
  it("schreibt eine Lücke über mehrere Jahre als Spanne", () => {
    expect(yearSpan({ year: 2025, year_to: 2025 })).toBe("2025");
    expect(yearSpan({ year: 2020, year_to: 2026 })).toBe("2020–2026");
  });
});

const card = (key: string, policy_field: string, field_label: string) =>
  ({ key, policy_field, field_label }) as PlanCard;

describe("byField", () => {
  it("schneidet an den Feldgrenzen und lässt die Reihenfolge stehen", () => {
    const groups = byField([
      card("a", "bildung", "Bildung"), card("b", "bildung", "Bildung"), card("c", "verkehr", "Verkehr"),
    ]);
    expect(groups.map((g) => [g.label, g.plans.map((p) => p.key)])).toEqual([
      ["Bildung", ["a", "b"]], ["Verkehr", ["c"]],
    ]);
  });
  it("kommt mit einer leeren Gruppe zurecht", () => {
    expect(byField([])).toEqual([]);
  });
});

const FIELDS: PlanMeasureField[] = [
  { field: "Mobilität", measures: [
    { code: "FußRad_01", title: "Raumerweiterung Fuß- und Radverkehr", package: "Fuß- und Fahrradverkehr", page: 2, status_raw: null, status_norm: null, status_quote: null, decision_count: 0 },
    { code: "FußRad_02", title: "Fahrradstraßen", package: "Fuß- und Fahrradverkehr", page: 2, status_raw: null, status_norm: null, status_quote: null, decision_count: 0 },
    { code: "ÖPNV_01", title: "Taktverdichtung", package: "ÖPNV", page: 2, status_raw: null, status_norm: null, status_quote: null, decision_count: 0 },
  ] },
  { field: "Stadtverwaltung", measures: [
    { code: "Verwaltung_01", title: "Klimagerechtes Beschaffungs- und Vergabewesen", package: null, page: 2, status_raw: null, status_norm: null, status_quote: null, decision_count: 0 },
  ] },
];

const codes = (fields: PlanMeasureField[]) => fields.flatMap((f) => f.measures.map((m) => m.code));

describe("filterMeasures", () => {
  it("gibt ohne Suche alles zurück", () => {
    expect(filterMeasures(FIELDS, "  ")).toEqual(FIELDS);
  });
  it("sucht in Kennung, Titel, Paket und Feld — ohne Rücksicht auf Umlaute und Großschreibung", () => {
    expect(codes(filterMeasures(FIELDS, "strasse"))).toEqual(["FußRad_02"]);
    expect(codes(filterMeasures(FIELDS, "OPNV"))).toEqual(["ÖPNV_01"]);
    expect(filterMeasures(FIELDS, "verwaltung_01")).toHaveLength(1);
    // Das Feld zählt mit: Wer „Mobilität“ tippt, bekommt alle Maßnahmen des Felds.
    expect(filterMeasures(FIELDS, "mobilität")[0].measures).toHaveLength(3);
  });
  it("verlangt jedes Wort und lässt Felder ohne Treffer weg", () => {
    expect(codes(filterMeasures(FIELDS, "rad raum"))).toEqual(["FußRad_01"]);
    expect(filterMeasures(FIELDS, "rad taktverdichtung")).toEqual([]);
  });
});

describe("byPackage", () => {
  it("schneidet an den Paketgrenzen", () => {
    expect(byPackage(FIELDS[0].measures).map((p) => [p.name, p.measures.length])).toEqual([
      ["Fuß- und Fahrradverkehr", 2], ["ÖPNV", 1],
    ]);
  });
  it("macht aus einem Feld ohne Pakete ein Stück", () => {
    expect(byPackage(FIELDS[1].measures)).toEqual([{ name: null, measures: FIELDS[1].measures }]);
  });
});

describe("statusLine", () => {
  const counts = [
    { status_raw: "Neu", status_norm: "open" as const, count: 0 },
    { status_raw: "In Umsetzung", status_norm: "in_progress" as const, count: 34 },
    { status_raw: "Realisiert", status_norm: "done" as const, count: 20 },
  ];
  it("zählt in den Worten der Stadt und lässt leere Stufen weg", () => {
    expect(statusLine({ counts, total: 54, complete: true })).toBe("34 In Umsetzung · 20 Realisiert");
  });
  it("nennt die Zählbasis, wenn die Stadt nur einen Teil einordnet", () => {
    expect(statusLine({ counts: [{ status_raw: "in Umsetzung", status_norm: "in_progress", count: 6 }], total: 18, complete: false }))
      .toBe("6 von 18 in Umsetzung");
  });
});

describe("signed", () => {
  it("schreibt Vorzeichen aus", () => {
    expect([signed(9), signed(-2), signed(0)]).toEqual(["+9", "−2", "±0"]);
  });
});

describe("statusLabels", () => {
  it("folgt dem jüngsten Stand und hängt alte Wörter an", () => {
    const series = [
      { counts: [{ status_raw: "In Planung" }, { status_raw: "Realisiert" }] },
      { counts: [{ status_raw: "Planung" }, { status_raw: "Realisiert" }] },
    ];
    expect(statusLabels(series)).toEqual(["Planung", "Realisiert", "In Planung"]);
  });
});

describe("formatAmount und formatChange", () => {
  it("setzt Tausenderpunkte", () => {
    expect([formatAmount(935792), formatAmount(1140000), formatAmount(950)]).toEqual(["935.792", "1.140.000", "950"]);
  });
  it("rundet die Änderung genau einmal auf eine Nachkommastelle", () => {
    expect(formatChange((935792 - 1140000) / 1140000)).toBe("−17,9 %");
    expect(formatChange((1083000 - 1140000) / 1140000)).toBe("−5,0 %");
    expect([formatChange(0.0504), formatChange(0)]).toEqual(["+5,0 %", "±0,0 %"]);
  });
});

describe("statusSummary", () => {
  it("lässt kurze Verteilungen stehen und fasst lange zusammen, ohne auszuwählen", () => {
    const short = { counts: [{ status_raw: "in Umsetzung", status_norm: "in_progress" as const, count: 6 }], total: 18, complete: false };
    expect(statusSummary(short)).toBe("6 von 18 in Umsetzung");
    const long = {
      total: 68, complete: true,
      counts: [100, 75, 50, 25, 0].map((stage, i) => ({
        status_raw: `eine lange Beschreibung der Stufe in den Worten der Stadt (Stufe ${stage} %)`,
        status_norm: "started" as const, count: [10, 6, 11, 16, 25][i] })),
    };
    expect(statusSummary(long)).toBe("68 Maßnahmen, von der Stadt in 5 Stufen eingeordnet");
  });
});

describe("squareTokens", () => {
  const counts = (pairs: [string, number][]) => ({ counts: pairs.map(([status_raw, count]) => ({ status_raw, count })) });
  const perLabel = (tokens: { label: string }[]) => {
    const out: Record<string, number> = {};
    for (const t of tokens) out[t.label] = (out[t.label] ?? 0) + 1;
    return out;
  };

  it("gibt je Stand genau die gemeldeten Summen wieder", () => {
    const series = [counts([["offen", 5], ["läuft", 2], ["fertig", 1]]), counts([["offen", 1], ["läuft", 4], ["fertig", 3]])];
    const tokens = squareTokens(series);
    expect(perLabel(tokens[0])).toEqual({ offen: 5, läuft: 2, fertig: 1 });
    expect(perLabel(tokens[1])).toEqual({ offen: 1, läuft: 4, fertig: 3 });
  });

  it("lässt stehen, was in seiner Stufe bleibt, und bewegt nur den Überschuss", () => {
    const [before, after] = squareTokens([counts([["offen", 5], ["fertig", 1]]), counts([["offen", 3], ["fertig", 3]])]);
    const stage = (tokens: { id: number; label: string }[]) => new Map(tokens.map((t) => [t.id, t.label]));
    const moved = [...stage(before)].filter(([id, label]) => stage(after).get(id) !== label);
    expect(moved).toHaveLength(2);
    expect(new Set(after.map((t) => t.id))).toEqual(new Set(before.map((t) => t.id)));
  });

  it("legt neue Kästchen an, wenn die Zählbasis wächst, und lässt welche fallen, wenn sie schrumpft", () => {
    const [a, b, c] = squareTokens([counts([["offen", 2]]), counts([["offen", 2], ["fertig", 2]]), counts([["fertig", 1]])]);
    expect(b).toHaveLength(4);
    expect(b.filter((t) => !a.some((x) => x.id === t.id))).toHaveLength(2);
    expect(c).toHaveLength(1);
    expect(b.some((t) => t.id === c[0].id)).toBe(true);
  });

  it("kommt mit einer Stufe zurecht, die die Stadt später anders nennt", () => {
    const [, after] = squareTokens([counts([["in Arbeit", 3]]), counts([["In Umsetzung", 3]])]);
    expect(perLabel(after)).toEqual({ "In Umsetzung": 3 });
    expect(after.map((t) => t.id)).toEqual([0, 1, 2]);
  });
});
