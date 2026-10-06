import { describe, expect, it } from "vitest";
import { nurHttps } from "./externer-link";

describe("nurHttps", () => {
  it("lässt https durch", () => {
    expect(nurHttps("https://www.oldenburg.de/x")).toBe("https://www.oldenburg.de/x");
  });
  it("verwirft javascript:, data:, http: und Relatives", () => {
    for (const roh of ["javascript:alert(1)", " JaVaScRiPt:alert(1)", "data:text/html,x", "http://evil.example", "/intern", "//evil.example"]) {
      expect(nurHttps(roh), roh).toBeUndefined();
    }
  });
  it("leer bleibt leer", () => {
    expect(nurHttps(null)).toBeUndefined();
    expect(nurHttps("")).toBeUndefined();
  });
});
