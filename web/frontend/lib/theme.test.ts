import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

// Das Farbschema hängt an drei Dingen gleichzeitig: dem gemerkten Wunsch, der
// Systemeinstellung und der Klasse am <html>. Die Fallstricke sind der
// System-Modus (er speichert NICHTS) und das Ereignis, das die drei Regler in
// der Oberfläche zusammenhält.

let speicher: ReturnType<typeof speicherStub>;
let dunkelSystem = false;
let klassen: Set<string>;
let ereignisse: string[];
let t: typeof import("./theme");

beforeEach(async () => {
  speicher = speicherStub();
  klassen = new Set<string>();
  ereignisse = [];
  dunkelSystem = false;
  vi.stubGlobal("localStorage", speicher);
  vi.stubGlobal("document", {
    documentElement: {
      classList: {
        toggle: (name: string, an: boolean) => (an ? klassen.add(name) : klassen.delete(name)),
        contains: (name: string) => klassen.has(name),
      },
    },
  });
  vi.stubGlobal("window", {
    matchMedia: () => ({ matches: dunkelSystem, addEventListener: () => {} }),
    dispatchEvent: (e: Event) => ereignisse.push(e.type),
    localStorage: speicher,
  });
  vi.resetModules();
  t = await import("./theme");
});

describe("getTheme", () => {
  it("ist ohne gemerkten Wunsch „system“", () => {
    expect(t.getTheme()).toBe("system");
  });

  it("liest den gemerkten Wunsch", () => {
    localStorage.setItem("theme", "dark");
    expect(t.getTheme()).toBe("dark");
  });
});

describe("applyTheme", () => {
  it("setzt die Klasse für „dark“ und nimmt sie für „light“ weg", () => {
    t.applyTheme("dark");
    expect(t.isDarkNow()).toBe(true);
    t.applyTheme("light");
    expect(t.isDarkNow()).toBe(false);
  });

  it("merkt sich eine ausdrückliche Wahl", () => {
    t.applyTheme("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
  });

  it("LÖSCHT den Eintrag im System-Modus, statt „system“ zu speichern", () => {
    // Sonst wäre der Wunsch ein dritter Wert im Speicher, und die App könnte
    // „folge dem System" nicht mehr von „noch nie entschieden" unterscheiden.
    localStorage.setItem("theme", "dark");
    t.applyTheme("system");
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("folgt im System-Modus wirklich dem System", () => {
    dunkelSystem = true;
    t.applyTheme("system");
    expect(t.isDarkNow()).toBe(true);
    dunkelSystem = false;
    t.applyTheme("system");
    expect(t.isDarkNow()).toBe(false);
  });

  it("ignoriert das System, wenn ausdrücklich gewählt wurde", () => {
    dunkelSystem = true;
    t.applyTheme("light");
    expect(t.isDarkNow()).toBe(false);
  });

  it("meldet jede Änderung — sonst laufen die drei Regler auseinander", () => {
    // Lotti-Schalter, Konto-Karte und ⌘K-Palette zeigen alle dasselbe.
    t.applyTheme("dark");
    expect(ereignisse).toContain(t.THEME_EVENT);
  });
});
