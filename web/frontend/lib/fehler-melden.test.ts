import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Wächter für den Fehler-Melder des Browsers.
 *
 * Geprüft wird vor allem, was NICHT rausgeht. Ein Melder, der die Suchanfrage
 * mitschickt, ist kein Werkzeug zur Fehlersuche mehr, sondern ein Protokoll
 * darüber, wer was gelesen hat — und niemand sähe es ihm an.
 */

type Aufruf = { url: string; init: RequestInit };

let aufrufe: Aufruf[];

/** Frisches Modul je Test: Zähler und Dublettenliste stehen im Modul. */
async function frisch(pfad = "/haushalt/schulden") {
  vi.resetModules();
  aufrufe = [];
  const zuhoerer: Record<string, (ev: unknown) => void> = {};
  vi.stubGlobal("window", {
    location: { pathname: pfad, search: "?q=geheim" },
    addEventListener: (name: string, f: (ev: unknown) => void) => {
      zuhoerer[name] = f;
    },
  });
  vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
    aufrufe.push({ url, init });
    return Promise.resolve({ ok: true } as Response);
  });
  const modul = await import("./fehler-melden");
  return { ...modul, zuhoerer };
}

function körper(a: Aufruf) {
  return JSON.parse(String(a.init.body));
}

beforeEach(() => {
  aufrufe = [];
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("was gemeldet wird", () => {
  it("schickt Typ, Meldung, Stapel und Pfad", async () => {
    const { meldeFehler } = await frisch();
    meldeFehler(new TypeError("x.y ist undefined"));
    expect(aufrufe).toHaveLength(1);
    const b = körper(aufrufe[0]);
    expect(b.name).toBe("TypeError");
    expect(b.message).toBe("x.y ist undefined");
    expect(b.route).toBe("/haushalt/schulden");
  });

  it("nimmt auch etwas an, das kein Error ist", async () => {
    const { meldeFehler } = await frisch();
    meldeFehler("nur ein String");
    expect(körper(aufrufe[0]).message).toContain("nur ein String");
  });
});

describe("was NICHT gemeldet wird", () => {
  it("keine Query — sie wäre die Suchanfrage", async () => {
    const { meldeFehler } = await frisch("/suche");
    meldeFehler(new Error("kaputt"));
    expect(JSON.stringify(körper(aufrufe[0]))).not.toContain("geheim");
    expect(körper(aufrufe[0]).route).toBe("/suche");
  });

  it("kein Cookie — die Meldung braucht kein Konto", async () => {
    const { meldeFehler } = await frisch();
    meldeFehler(new Error("kaputt"));
    expect(aufrufe[0].init.credentials).toBeUndefined();
  });

  it("kein Feld über den Browser selbst", async () => {
    const { meldeFehler } = await frisch();
    meldeFehler(new Error("kaputt"));
    const felder = Object.keys(körper(aufrufe[0])).sort();
    expect(felder).toEqual(["message", "name", "route", "stack"]);
  });

  it("der Stapel bleibt kurz", async () => {
    const { meldeFehler } = await frisch();
    const e = new Error("kaputt");
    e.stack = Array.from({ length: 40 }, (_, i) => `    at f${i} (/a.js:${i}:1)`).join("\n");
    meldeFehler(e);
    expect(körper(aufrufe[0]).stack.split("\n").length).toBeLessThanOrEqual(8);
  });
});

describe("er darf nie stören", () => {
  it("dieselbe Meldung geht nur einmal raus", async () => {
    const { meldeFehler } = await frisch();
    for (let i = 0; i < 5; i++) meldeFehler(new Error("gleich"));
    expect(aufrufe).toHaveLength(1);
  });

  it("eine kaputte Schleife wird gedeckelt", async () => {
    const { meldeFehler } = await frisch();
    for (let i = 0; i < 50; i++) meldeFehler(new Error(`nummer ${i}`));
    expect(aufrufe.length).toBeLessThanOrEqual(5);
  });

  it("wirft nicht, wenn der Versand scheitert", async () => {
    const { meldeFehler } = await frisch();
    vi.stubGlobal("fetch", () => {
      throw new Error("offline");
    });
    expect(() => meldeFehler(new Error("kaputt"))).not.toThrow();
  });

  it("hängt sich nur einmal an", async () => {
    const { fehlerMelderAnhaengen, zuhoerer } = await frisch();
    fehlerMelderAnhaengen();
    fehlerMelderAnhaengen();
    expect(Object.keys(zuhoerer).sort()).toEqual(["error", "unhandledrejection"]);
  });

  it("meldet keinen Ladefehler einer Datei", async () => {
    // `<img src=…>` schlägt im Netz des Besuchers fehl, nicht in unserem Code.
    const { fehlerMelderAnhaengen, zuhoerer } = await frisch();
    fehlerMelderAnhaengen();
    zuhoerer.error({ error: undefined });
    expect(aufrufe).toHaveLength(0);
    zuhoerer.error({ error: new Error("echt") });
    expect(aufrufe).toHaveLength(1);
  });
});
