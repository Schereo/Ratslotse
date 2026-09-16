import { describe, expect, it } from "vitest";
import { analysePfad, stimmenanteil } from "./stichwahl-analyse";

describe("Bezugsgrößen der Wahlanalyse", () => {
  it("ändert nur den Nenner, nicht die abgegebenen Stimmen", () => {
    expect(stimmenanteil(9447, 27122, 18499, "alle")).toBeCloseTo(34.8315, 4);
    expect(stimmenanteil(9447, 27122, 18499, "finalisten")).toBeCloseTo(51.0676, 4);
  });
  it("unterscheidet null Stimmen von einem fehlenden Nenner", () => {
    expect(stimmenanteil(0, 100, 0, "alle")).toBe(0);
    expect(stimmenanteil(0, 100, 0, "finalisten")).toBeNull();
  });
  it("kodiert den Link-Token als einen Parameter", () => {
    const p = new URL(analysePfad("test&cdu=100,0"), "https://example.org").searchParams;
    expect([...p.keys()]).toEqual(["token"]);
    expect(p.get("token")).toBe("test&cdu=100,0");
  });
});
