import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { breiteFuer, huellenKlasse, ULTRA_BREIT, VOLLBREIT } from "./vollbreit";

describe("breiteFuer", () => {
  it("kennt die Karte als randlos, auch mit Schrägstrich aus dem Export", () => {
    expect(breiteFuer("/karte")).toBe("voll");
    expect(breiteFuer("/karte/")).toBe("voll");
  });

  it("lässt jede nicht angemeldete Seite beim bisherigen Deckel", () => {
    expect(breiteFuer("/council")).toBe("normal");
    expect(breiteFuer(null)).toBe("normal");
  });

  it("gibt randlos weder Deckel noch Polster", () => {
    const k = huellenKlasse("voll");
    expect(k).not.toMatch(/max-w-/);
    expect(k).not.toMatch(/\bp[xy]-/);
  });

  it("hebt den Deckel nur für angemeldete Seiten auf 2200 px", () => {
    expect(huellenKlasse("ultra")).toContain("ultra:max-w-[2200px]");
    expect(huellenKlasse("normal")).not.toContain("ultra:");
  });
});

// Ein Tippfehler in der Liste wäre dauerhaft wirkungslos und sähe aus wie
// „noch nicht umgestellt" — deshalb muss jeder Eintrag eine echte Seite sein.
describe("die Listen zeigen auf echte Seiten", () => {
  it.each([...VOLLBREIT, ...ULTRA_BREIT])("%s", (pfad) => {
    expect(existsSync(join(__dirname, "..", "app", "(app)", pfad, "page.tsx"))).toBe(true);
  });

  it("führt keine Seite in beiden Listen", () => {
    expect(VOLLBREIT.filter((p) => ULTRA_BREIT.includes(p))).toEqual([]);
  });
});
