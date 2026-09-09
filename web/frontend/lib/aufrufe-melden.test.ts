import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Wächter für die Seitenzählung im Browser.
 *
 * Wie beim Fehler-Melder ist der wichtigere Teil, was NICHT rausgeht. Dieser
 * Melder feuert bei JEDEM Seitenwechsel — wenn er die Query mitschickte, wäre
 * er ein Protokoll darüber, wer welchen Beschluss gelesen und wonach gesucht
 * hat, und niemand sähe es ihm an.
 */

type Aufruf = { url: string; init: RequestInit };

let aufrufe: Aufruf[];

/** Frisches Modul je Test: die Dublettensperre steht im Modul. */
async function frisch(tabMarke: string | null = null) {
  vi.resetModules();
  aufrufe = [];
  const speicher: Record<string, string> = {};
  if (tabMarke) speicher["ratslotse.aufruf-gesehen"] = tabMarke;
  vi.stubGlobal("window", {
    location: { pathname: "/council", search: "?q=geheim&id=8525" },
    sessionStorage: {
      getItem: (k: string) => speicher[k] ?? null,
      setItem: (k: string, v: string) => {
        speicher[k] = v;
      },
    },
  });
  vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
    aufrufe.push({ url, init });
    return Promise.resolve({ ok: true } as Response);
  });
  return await import("./aufrufe-melden");
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
  it("schickt Route, Client und den Anmeldestatus als Ja/Nein", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/haushalt/schulden", true, "ios");
    expect(aufrufe).toHaveLength(1);
    const b = körper(aufrufe[0]);
    expect(b).toEqual({
      route: "/haushalt/schulden",
      client: "ios",
      first: true,
      logged_in: true,
    });
  });

  it("meldet den ersten Aufruf im Tab als Besuch, den zweiten nicht", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/", false);
    meldeAufruf("/fragen", false);
    expect(körper(aufrufe[0]).first).toBe(true);
    expect(körper(aufrufe[1]).first).toBe(false);
  });

  it("zählt in einem Tab mit vorhandener Marke keinen neuen Besuch", async () => {
    const { meldeAufruf } = await frisch("1");
    meldeAufruf("/", false);
    expect(körper(aufrufe[0]).first).toBe(false);
  });

  it("meldet denselben Pfad nicht zweimal hintereinander", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/fragen", false);
    meldeAufruf("/fragen", false);
    expect(aufrufe).toHaveLength(1);
  });
});

describe("was NICHT rausgeht", () => {
  it("schickt kein Cookie mit", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/", false);
    // Ohne Cookie kann der Server die Zählung keinem Konto zuordnen, selbst
    // wenn er wollte. `logged_in` ist ein Ja/Nein, keine Kennung.
    expect(aufrufe[0].init.credentials).toBeUndefined();
  });

  it("nimmt die Query nicht aus der Adresszeile", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/council", false);
    const roh = String(aufrufe[0].init.body);
    expect(roh).not.toContain("geheim");
    expect(roh).not.toContain("8525");
  });

  it("schickt weder Referrer noch User-Agent noch eine Kennung", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/", true);
    expect(Object.keys(körper(aufrufe[0])).sort()).toEqual([
      "client", "first", "logged_in", "route",
    ]);
  });

  it("kürzt einen übermäßig langen Pfad", async () => {
    const { meldeAufruf } = await frisch();
    meldeAufruf("/" + "a".repeat(500), false);
    expect(körper(aufrufe[0]).route.length).toBe(200);
  });
});

describe("er darf nie stören", () => {
  it("verschluckt einen Fehler beim Senden", async () => {
    const { meldeAufruf } = await frisch();
    vi.stubGlobal("fetch", () => {
      throw new Error("offline");
    });
    expect(() => meldeAufruf("/", false)).not.toThrow();
  });

  it("kommt ohne sessionStorage aus (privates Fenster)", async () => {
    vi.resetModules();
    aufrufe = [];
    vi.stubGlobal("window", {
      location: { pathname: "/", search: "" },
      sessionStorage: {
        getItem: () => {
          throw new Error("blockiert");
        },
        setItem: () => {
          throw new Error("blockiert");
        },
      },
    });
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      aufrufe.push({ url, init });
      return Promise.resolve({ ok: true } as Response);
    });
    const { meldeAufruf } = await import("./aufrufe-melden");
    meldeAufruf("/", false);
    expect(aufrufe).toHaveLength(1);
    expect(körper(aufrufe[0]).first).toBe(false);
  });
});
