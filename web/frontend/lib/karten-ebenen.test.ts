import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

// Die Ebenen-Chips der Stadtkarte haben zwei Gedächtnisse — Adresse und
// localStorage — und eine Vorgabe. Was hier zählt: Die Adresse gewinnt, ein
// geteilter Link zeigt also, was der Absender sah; die Vorgabe hält die
// Adresse sauber; ein gesperrter Speicher (privates Fenster) bricht nichts.

let speicher: ReturnType<typeof speicherStub>;
let m: typeof import("./karten-ebenen");

beforeEach(async () => {
  speicher = speicherStub();
  vi.stubGlobal("window", { localStorage: speicher });
  vi.resetModules();
  m = await import("./karten-ebenen");
});

describe("ebenenAusUrl / ebenenZuUrl", () => {
  it("liest die Adresse und verwirft Unbekanntes", () => {
    expect([...m.ebenenAusUrl("vorhaben, plaene,quatsch")!]).toEqual(["vorhaben", "plaene"]);
    expect(m.ebenenAusUrl("")!.size).toBe(0);
    expect(m.ebenenAusUrl(null)).toBeNull();
  });
  it("hält die Adresse sauber, solange die Vorgabe gilt", () => {
    expect(m.ebenenZuUrl(new Set(m.ALLE_EBENEN))).toBeNull();
    expect(m.ebenenZuUrl(new Set(["sperrungen", "vorhaben"]))).toBe("vorhaben,sperrungen");
    expect(m.ebenenZuUrl(new Set())).toBe("");
  });
});

describe("ebenenStart", () => {
  it("Adresse vor Speicher vor Vorgabe", () => {
    expect([...m.ebenenStart(null)]).toEqual([...m.ALLE_EBENEN]);
    m.ebenenMerken(new Set(["vorhaben"]));
    expect([...m.ebenenStart(null)]).toEqual(["vorhaben"]);
    expect([...m.ebenenStart("plaene")]).toEqual(["plaene"]);
    // Eine leere Adresse heißt „keine", nicht „Vorgabe".
    expect(m.ebenenStart("").size).toBe(0);
  });
  it("überlebt einen gesperrten Speicher und kaputtes JSON", () => {
    speicher.setItem("karte.ebenen", "{nicht json");
    expect([...m.ebenenStart(null)]).toEqual([...m.ALLE_EBENEN]);
    speicher.kaputt(true);
    expect(() => m.ebenenMerken(new Set(["plaene"]))).not.toThrow();
    expect([...m.ebenenStart(null)]).toEqual([...m.ALLE_EBENEN]);
  });
});

describe("ebeneUmschalten", () => {
  it("schaltet um, ohne das Original anzufassen", () => {
    const a = new Set<"vorhaben" | "plaene" | "sperrungen">(["vorhaben"]);
    const b = m.ebeneUmschalten(a, "plaene");
    expect([...b]).toEqual(["vorhaben", "plaene"]);
    expect([...m.ebeneUmschalten(b, "vorhaben")]).toEqual(["plaene"]);
    expect([...a]).toEqual(["vorhaben"]);
  });
});
