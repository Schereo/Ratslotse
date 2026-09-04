import { beforeEach, describe, expect, it, vi } from "vitest";

// Die Weiche zwischen Browser und nativer Hülle. Sie entscheidet die
// BASIS-ADRESSE jedes Aufrufs und die Client-Marke — beides Dinge, die man
// erst bemerkt, wenn die App gar nichts mehr lädt.

let plattform = "web";
let nativ = false;
vi.mock("@capacitor/core", () => ({
  Capacitor: {
    isNativePlatform: () => {
      if (plattform === "kaputt") throw new Error("Capacitor fehlt");
      return nativ;
    },
    getPlatform: () => {
      if (plattform === "kaputt") throw new Error("Capacitor fehlt");
      return plattform;
    },
  },
}));

let p: typeof import("./platform");
beforeEach(async () => {
  plattform = "web"; nativ = false;
  vi.resetModules();
  vi.unstubAllEnvs();
  p = await import("./platform");
});

describe("isNativeApp", () => {
  it("ist im Browser falsch", () => {
    expect(p.isNativeApp()).toBe(false);
  });

  it("ist in der App wahr", () => {
    nativ = true; plattform = "ios";
    expect(p.isNativeApp()).toBe(true);
  });

  it("sagt „Browser“, wenn Capacitor gar nicht da ist", () => {
    // Der Fehlerfall MUSS in Richtung Web zeigen: Ein Wurf hier bräche jeden
    // Aufruf der App, statt sie nur anders zu adressieren.
    plattform = "kaputt";
    expect(p.isNativeApp()).toBe(false);
  });
});

describe("nativePlatform", () => {
  it.each([["ios", "ios"], ["android", "android"], ["web", null], ["windows", null]])(
    "%s → %s", (roh, erwartet) => {
      plattform = roh;
      expect(p.nativePlatform()).toBe(erwartet);
    });

  it("liefert null statt zu werfen", () => {
    plattform = "kaputt";
    expect(p.nativePlatform()).toBeNull();
  });
});

describe("clientMarke", () => {
  it("nennt die Plattform", () => {
    plattform = "ios";
    expect(p.clientMarke()).toBe("ios");
  });

  it("fällt auf „app“ zurück — NIE auf „web“", () => {
    // Der Wert muss nativ bleiben: Bekäme die Anmeldung „web", gäbe es nur
    // ein Cookie statt des Bearer-Tokens, das die App braucht.
    plattform = "kaputt";
    expect(p.clientMarke()).toBe("app");
    expect(["ios", "android", "app"]).toContain(p.clientMarke());
  });
});

describe("apiBase", () => {
  it("ist im Web leer — gleiche Herkunft, /api wird weitergeleitet", () => {
    expect(p.apiBase()).toBe("");
  });

  it("ist in der App absolut", async () => {
    nativ = true; plattform = "ios";
    vi.resetModules(); p = await import("./platform");
    expect(p.apiBase()).toBe("https://ratslotse.de");
  });

  it("lässt sich für den Simulator umbiegen", async () => {
    nativ = true; plattform = "ios";
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://192.168.1.5:8000");
    vi.resetModules(); p = await import("./platform");
    expect(p.apiBase()).toBe("http://192.168.1.5:8000");
  });
});
