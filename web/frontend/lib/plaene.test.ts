import { describe, expect, it } from "vitest";
import { datum, gremien, stationsArt, statusTon } from "./plaene";

describe("datum", () => {
  it("dreht ISO-Daten ohne Zeitzone um", () => {
    expect(datum("2022-12-19")).toBe("19.12.2022");
    expect(datum("2029-09")).toBe("09/2029");
    expect(datum("2035")).toBe("2035");
  });
});

describe("stationsArt", () => {
  it("nennt mündliche Berichte als solche", () => {
    expect(stationsArt({ kind: "report", oral: true })).toBe("Mündlicher Bericht, ohne Text");
    expect(stationsArt({ kind: "report", oral: false })).toBe("Bericht");
    expect(stationsArt({ kind: "adoption", oral: false })).toBe("Beschluss des Plans");
  });
});

describe("gremien", () => {
  it("stellt den Rat ans Ende", () => {
    expect(gremien(["Rat", "Sozialausschuss"])).toBe("Sozialausschuss · Rat");
    expect(gremien(["Jugendhilfeausschuss"])).toBe("Jugendhilfeausschuss");
  });
});

describe("statusTon", () => {
  it("kennt keinen Fehler-Ton", () => {
    expect(statusTon("expired")).toBe("neutral");
    expect(statusTon("superseded")).toBe("neutral");
    expect(statusTon("preparing")).toBe("primary");
    expect(statusTon("running")).toBe("none");
  });
});
