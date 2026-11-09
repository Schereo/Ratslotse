import { describe, expect, it } from "vitest";
import {
  byField, byPackage, committeeList, filterMeasures, formatDate, percent, reportCount, stationKind, statusTone, yearSpan,
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
    { code: "FußRad_01", title: "Raumerweiterung Fuß- und Radverkehr", package: "Fuß- und Fahrradverkehr", page: 2 },
    { code: "FußRad_02", title: "Fahrradstraßen", package: "Fuß- und Fahrradverkehr", page: 2 },
    { code: "ÖPNV_01", title: "Taktverdichtung", package: "ÖPNV", page: 2 },
  ] },
  { field: "Stadtverwaltung", measures: [
    { code: "Verwaltung_01", title: "Klimagerechtes Beschaffungs- und Vergabewesen", package: null, page: 2 },
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
