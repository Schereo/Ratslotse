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
  it("verwirft, was Server und Browser verschieden lesen", () => {
    for (const roh of [
      "https://evil.example\\@www.oldenburg.de/",
      "https://phish.example\\.oldenburg.de/login",
      "https://nutzer@example.org/",
      "https://www.oldenburg.de/a b",
      "https://www.oldenburg.de/\tx",
    ]) {
      expect(nurHttps(roh), roh).toBeUndefined();
    }
  });
  it("liefert die aufgelöste Form", () => {
    expect(nurHttps("https://WWW.Oldenburg.de/x")).toBe("https://www.oldenburg.de/x");
  });
  it("leer bleibt leer", () => {
    expect(nurHttps(null)).toBeUndefined();
    expect(nurHttps("")).toBeUndefined();
  });
});
