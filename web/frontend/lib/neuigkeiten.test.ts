import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";
import type { Highlight, Release } from "./neuigkeiten";

let speicher: ReturnType<typeof speicherStub>;

beforeEach(() => {
  speicher = speicherStub();
  vi.stubGlobal("localStorage", speicher);
  vi.stubGlobal("window", { localStorage: speicher });
  vi.resetModules();
});

const laden = () => import("./neuigkeiten");

function hl(title: string, extra: Partial<Highlight> = {}): Highlight {
  return {
    title, text: "…", url: `/${title.toLowerCase()}`,
    media: { kind: "video", src: "/c.mp4", alt: "x", aspect: "16/9", poster: "/c.webp", cover: "/c.webp", duration: 20 },
    color: "primary", aside: false, tagline: null, action: "Ausprobieren",
    ...extra,
  };
}

function rel(highlights: Highlight[]): Release {
  return { version: "3.0.0", date: "2026-10-06", title: "Das Lotti-Update", teaser: null, highlights };
}

describe("Kachelfarbe", () => {
  it("übersetzt die drei Namen der Registry in die Werte der Designsprache", async () => {
    const n = await laden();
    expect(n.kachelFarbe("signal")).toBe("#ce4709");
    expect(n.kachelFarbe("primary")).toBe("#0764a6");
    expect(n.kachelFarbe("green")).toBe("#15803d");
  });

  it("fällt bei einem unbekannten Namen auf Hafenblau zurück statt auf nichts", async () => {
    const n = await laden();
    expect(n.kachelFarbe("lila")).toBe(n.KACHEL_FARBEN.primary);
    expect(n.kachelFarbe(null)).toBe(n.KACHEL_FARBEN.primary);
    // Kein Prototyp-Schlüssel rutscht als Farbe durch.
    expect(n.kachelFarbe("toString")).toBe(n.KACHEL_FARBEN.primary);
  });
});

describe("Dauer", () => {
  it("rundet auf ganze Sekunden und schreibt m:ss", async () => {
    const n = await laden();
    expect(n.formatDauer(20)).toBe("0:20");
    expect(n.formatDauer(17.47)).toBe("0:17");
    expect(n.formatDauer(17.5)).toBe("0:18");
    expect(n.formatDauer(65)).toBe("1:05");
    expect(n.formatDauer(0.3)).toBe("0:01");
  });

  it("zeigt nichts, wenn niemand die Länge gemessen hat", async () => {
    const n = await laden();
    expect(n.formatDauer(null)).toBeNull();
    expect(n.formatDauer(undefined)).toBeNull();
    expect(n.formatDauer(0)).toBeNull();
    expect(n.formatDauer(Number.NaN)).toBeNull();
  });

  it("spricht die Länge für Screenreader aus", async () => {
    const n = await laden();
    expect(n.dauerGesprochen(24)).toBe("24 Sekunden");
    expect(n.dauerGesprochen(61)).toBe("1 Minute 1 Sekunde");
    expect(n.dauerGesprochen(120)).toBe("2 Minuten");
  });
});

describe("Kacheln und Nebenbei", () => {
  it("trennt die Nebenbei-Zeilen ab und hält die Reihenfolge", async () => {
    const n = await laden();
    const { kacheln, nebenbei } = n.aufteilen([hl("A"), hl("Akte", { aside: true }), hl("B")]);
    expect(kacheln.map((h) => h.title)).toEqual(["A", "B"]);
    expect(nebenbei.map((h) => h.title)).toEqual(["Akte"]);
  });

  it("zeigt Kacheln nur, wenn jedes Highlight ein Medium hat", async () => {
    const n = await laden();
    expect(n.mitKacheln(rel([hl("A"), hl("B")]))).toBe(true);
    expect(n.mitKacheln(rel([hl("A"), hl("B", { media: null })]))).toBe(false);
    // Nur Nebenbei-Highlights: keine einzige Kachel — dann die Liste.
    expect(n.mitKacheln(rel([hl("A", { aside: true })]))).toBe(false);
    expect(n.mitKacheln(undefined)).toBe(false);
  });

  it("beginnt „Los“ bei der ersten noch nicht angesehenen Kachel", async () => {
    const n = await laden();
    const k = [hl("A"), hl("B"), hl("C")];
    const gesehen = new Set([n.highlightSchluessel(k[0]), n.highlightSchluessel(k[2])]);
    expect(n.ersteUngesehene(k, gesehen)).toBe(1);
    expect(n.zaehleGesehen(k, gesehen)).toBe(2);
    expect(n.ersteUngesehene(k, new Set(k.map(n.highlightSchluessel)))).toBe(0);
  });
});

describe("Angesehen merken", () => {
  it("merkt je Ausgabe, was schon aufgeschlagen war — auch über ein Neuladen", async () => {
    const n = await laden();
    n.gesehenMerken("3.0.0", "/karte#Mein Viertel");
    n.gesehenMerken("3.0.0", "/karte#Mein Viertel");
    n.gesehenMerken("4.0.0", "/x#Y");
    const frisch = await laden();
    expect([...frisch.gesehenLesen("3.0.0")]).toEqual(["/karte#Mein Viertel"]);
    expect([...frisch.gesehenLesen("4.0.0")]).toEqual(["/x#Y"]);
  });

  it("ein gesperrter Speicher (privates Fenster) ist kein Fehler", async () => {
    const n = await laden();
    speicher.kaputt(true);
    expect(() => n.gesehenMerken("3.0.0", "a")).not.toThrow();
    // Der Stand des Aufrufs stimmt trotzdem — die Seite zeigt den Haken.
    expect([...n.gesehenMerken("3.0.0", "a")]).toEqual(["a"]);
    expect(n.gesehenLesen("3.0.0").size).toBe(0);
  });

  it("Müll im Speicher heißt: nichts gesehen", async () => {
    const n = await laden();
    speicher.setItem("ratslotse.neuigkeiten.gesehen.3.0.0", "{kaputt");
    expect(n.gesehenLesen("3.0.0").size).toBe(0);
    speicher.setItem("ratslotse.neuigkeiten.gesehen.3.0.0", JSON.stringify(["a", 3, null]));
    expect([...n.gesehenLesen("3.0.0")]).toEqual(["a"]);
  });
});

describe("Spieler", () => {
  it("liest das Seitenverhältnis aus dem Medium", async () => {
    const n = await laden();
    expect(n.seitenVerhaeltnis("16/9")).toBeCloseTo(16 / 9);
    expect(n.seitenVerhaeltnis("1206/2622")).toBeCloseTo(0.46, 2);
    expect(n.seitenVerhaeltnis("quatsch")).toBeCloseTo(16 / 9);
    expect(n.seitenVerhaeltnis(null)).toBeCloseTo(16 / 9);
  });

  it("schaltet am Ende eines Clips weiter — nur mit Bewegung und nur bis zum letzten", async () => {
    const n = await laden();
    expect(n.nachDemEnde({ index: 0, anzahl: 3, ruhig: false, nebenbei: false })).toBe("weiter");
    expect(n.nachDemEnde({ index: 2, anzahl: 3, ruhig: false, nebenbei: false })).toBe("stehen");
    // prefers-reduced-motion: kein Selbstlauf, auch nicht am Ende.
    expect(n.nachDemEnde({ index: 0, anzahl: 3, ruhig: true, nebenbei: false })).toBe("stehen");
    // Ein Nebenbei-Clip steht allein.
    expect(n.nachDemEnde({ index: 0, anzahl: 1, ruhig: false, nebenbei: true })).toBe("stehen");
  });
});
