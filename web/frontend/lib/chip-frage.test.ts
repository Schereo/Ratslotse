import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

let speicher: ReturnType<typeof speicherStub>;
let c: typeof import("./chip-frage");

beforeEach(async () => {
  speicher = speicherStub();
  vi.stubGlobal("sessionStorage", speicher);
  vi.resetModules();
  c = await import("./chip-frage");
});

describe("chip-frage", () => {
  it("ohne Antippen keine sofortige Frage — ein Link allein reicht nicht", () => {
    expect(c.chipEinloesen("Was kostet das Stadion?")).toBe(false);
  });
  it("angetippt: genau einmal", () => {
    c.chipMerken("Was kostet das Stadion?");
    expect(c.chipEinloesen("Was kostet das Stadion?")).toBe(true);
    expect(c.chipEinloesen("Was kostet das Stadion?")).toBe(false);
  });
  it("eine andere Frage als die angetippte gilt nicht", () => {
    c.chipMerken("Was kostet das Stadion?");
    expect(c.chipEinloesen("Etwas ganz anderes")).toBe(false);
  });
  it("verfällt nach zehn Minuten", () => {
    const jetzt = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(jetzt);
    c.chipMerken("Frage");
    vi.spyOn(Date, "now").mockReturnValue(jetzt + 11 * 60 * 1000);
    expect(c.chipEinloesen("Frage")).toBe(false);
    vi.restoreAllMocks();
  });
  it("ein gesperrter Speicher ist kein Absturz", () => {
    speicher.kaputt(true);
    c.chipMerken("Frage");
    expect(c.chipEinloesen("Frage")).toBe(false);
  });
});
