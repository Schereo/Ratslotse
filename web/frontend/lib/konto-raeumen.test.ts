import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

let sitzung: ReturnType<typeof speicherStub>;
let lokal: ReturnType<typeof speicherStub>;
let k: typeof import("./konto-raeumen");

beforeEach(async () => {
  sitzung = speicherStub();
  lokal = speicherStub();
  vi.stubGlobal("sessionStorage", sitzung);
  vi.stubGlobal("localStorage", lokal);
  vi.resetModules();
  k = await import("./konto-raeumen");
  sitzung.setItem("ratslotse:lotti-verlauf", "[…]");
  sitzung.setItem("ratslotse:qa-gespraech", "12");
  sitzung.setItem("ratslotse:entwurf", "{…}");
  sitzung.setItem("ratslotse:theme", "dunkel");
  lokal.setItem(k.QUERY_CACHE, "{…}");
});

describe("kontoDatenRaeumen", () => {
  it("räumt beim Abmelden Gespräche, Entwurf und Abfrage-Cache", () => {
    k.kontoDatenRaeumen({ mitEntwurf: true });
    expect(sitzung.getItem("ratslotse:lotti-verlauf")).toBeNull();
    expect(sitzung.getItem("ratslotse:qa-gespraech")).toBeNull();
    expect(sitzung.getItem("ratslotse:entwurf")).toBeNull();
    expect(lokal.getItem(k.QUERY_CACHE)).toBeNull();
    // Was nicht am Konto hängt, bleibt.
    expect(sitzung.getItem("ratslotse:theme")).toBe("dunkel");
  });
  it("behält beim Ablauf der Sitzung den geretteten Entwurf", () => {
    k.kontoDatenRaeumen({ mitEntwurf: false });
    expect(sitzung.getItem("ratslotse:entwurf")).toBe("{…}");
    expect(sitzung.getItem("ratslotse:lotti-verlauf")).toBeNull();
  });
  it("ein gesperrter Speicher ist kein Absturz", () => {
    sitzung.kaputt(true);
    lokal.kaputt(true);
    expect(() => k.kontoDatenRaeumen({ mitEntwurf: true })).not.toThrow();
  });
});
