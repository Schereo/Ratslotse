import { describe, expect, it } from "vitest";
import { ratsjahre } from "./ratsjahre";

describe("ratsjahre", () => {
  it("fasst aufeinanderfolgende Perioden zusammen", () => {
    expect(ratsjahre([2001, 2006, 2011, 2016, 2021], 2021)).toBe("seit 2001");
  });
  it("zeigt eine Lücke als zwei Spannen", () => {
    expect(ratsjahre([2011, 2021], 2021)).toBe("2011–2016, seit 2021");
  });
  it("früher im Rat, zuletzt nicht", () => {
    expect(ratsjahre([2016], 2021)).toBe("2016–2021");
  });
  it("ohne Perioden leer", () => {
    expect(ratsjahre([], 2021)).toBe("");
  });
});
