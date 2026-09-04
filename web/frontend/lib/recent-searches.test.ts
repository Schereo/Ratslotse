import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

let speicher: ReturnType<typeof speicherStub>;
let r: typeof import("./recent-searches");

beforeEach(async () => {
  speicher = speicherStub();
  vi.stubGlobal("localStorage", speicher);
  vi.resetModules();
  r = await import("./recent-searches");
});

describe("pushRecentSearch", () => {
  it("merkt einen Begriff, neueste zuerst", () => {
    r.pushRecentSearch("radwege");
    r.pushRecentSearch("stadion");
    expect(r.getRecentSearches()).toEqual(["stadion", "radwege"]);
  });

  it("wirft Präfixe des neuen Begriffs raus — die Liste zeigt Ziele, nicht Wege", () => {
    // Beim Tippen mit Debounce entstehen unterwegs „rad" und „radweg".
    r.pushRecentSearch("rad");
    r.pushRecentSearch("radweg");
    r.pushRecentSearch("radwege");
    expect(r.getRecentSearches()).toEqual(["radwege"]);
  });

  it("behält einen Begriff, der KEIN Präfix ist", () => {
    r.pushRecentSearch("radwege");
    r.pushRecentSearch("stadion");
    expect(r.getRecentSearches()).toHaveLength(2);
  });

  it("entfernt eine Dublette, statt sie zweimal zu führen", () => {
    r.pushRecentSearch("stadion");
    r.pushRecentSearch("radwege");
    r.pushRecentSearch("stadion");
    expect(r.getRecentSearches()).toEqual(["stadion", "radwege"]);
  });

  it("vergleicht ohne Rücksicht auf Groß- und Kleinschreibung", () => {
    r.pushRecentSearch("Stadion");
    r.pushRecentSearch("stadion");
    expect(r.getRecentSearches()).toEqual(["stadion"]);
  });

  it("hält höchstens fünf", () => {
    for (const q of ["eins", "zwei", "drei", "vier", "fünf", "sechs"]) r.pushRecentSearch(q);
    const liste = r.getRecentSearches();
    expect(liste).toHaveLength(5);
    expect(liste[0]).toBe("sechs");
    expect(liste).not.toContain("eins");
  });

  it("ignoriert zu Kurzes und Leeres", () => {
    for (const q of ["ab", "", "   ", "  a "]) r.pushRecentSearch(q);
    expect(r.getRecentSearches()).toEqual([]);
  });

  it("speichert getrimmt", () => {
    r.pushRecentSearch("  radwege  ");
    expect(r.getRecentSearches()).toEqual(["radwege"]);
  });

  it("wirft nicht, wenn der Speicher gesperrt ist", () => {
    speicher.kaputt(true);
    expect(() => r.pushRecentSearch("radwege")).not.toThrow();
    expect(r.getRecentSearches()).toEqual([]);
  });
});

describe("getRecentSearches", () => {
  it("liefert eine leere Liste, wenn nichts da ist", () => {
    expect(r.getRecentSearches()).toEqual([]);
  });

  it("verträgt kaputten Inhalt", () => {
    localStorage.setItem("ratslotse:recent-searches", "{kein json");
    expect(r.getRecentSearches()).toEqual([]);
  });

  it("wirft Nicht-Zeichenketten weg, statt sie zu rendern", () => {
    localStorage.setItem("ratslotse:recent-searches", JSON.stringify(["ok", 42, null, { a: 1 }]));
    expect(r.getRecentSearches()).toEqual(["ok"]);
  });

  it("verträgt einen Wert, der gar keine Liste ist", () => {
    localStorage.setItem("ratslotse:recent-searches", JSON.stringify({ a: 1 }));
    expect(r.getRecentSearches()).toEqual([]);
  });
});

describe("clearRecentSearches", () => {
  it("räumt auf", () => {
    r.pushRecentSearch("radwege");
    r.clearRecentSearches();
    expect(r.getRecentSearches()).toEqual([]);
  });

  it("wirft nicht bei gesperrtem Speicher", () => {
    speicher.kaputt(true);
    expect(() => r.clearRecentSearches()).not.toThrow();
  });
});
