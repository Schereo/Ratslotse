import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

// Drei kleine Speicher, die dasselbe Muster teilen: Sie machen die Oberfläche
// schneller, dürfen aber nie ein Fehler sein. Ein gesperrter Speicher (privates
// Fenster) muss zu „weiß ich nicht" führen, nicht zu einem Absturz.

let speicher: ReturnType<typeof speicherStub>;

beforeEach(() => {
  speicher = speicherStub();
  vi.stubGlobal("localStorage", speicher);
  vi.stubGlobal("window", { localStorage: speicher });
  vi.resetModules();
});

describe("recent — zuletzt angesehene Beschlüsse", () => {
  const laden = () => import("./recent");
  const b = (id: number, title: string) =>
    ({ id, title, committee: "Rat", session_date: "2026-08-20" });

  it("merkt neueste zuerst", async () => {
    const r = await laden();
    r.trackRecentDecision(b(1, "Eins"));
    r.trackRecentDecision(b(2, "Zwei"));
    expect((await laden()).getRecentDecisions().map((x) => x.id)).toEqual([2, 1]);
  });

  it("führt einen Beschluss nur einmal — der zweite Besuch rückt ihn nach vorn", async () => {
    const r = await laden();
    r.trackRecentDecision(b(1, "Eins"));
    r.trackRecentDecision(b(2, "Zwei"));
    r.trackRecentDecision(b(1, "Eins"));
    expect(r.getRecentDecisions().map((x) => x.id)).toEqual([1, 2]);
  });

  it("hält höchstens acht", async () => {
    const r = await laden();
    for (let i = 1; i <= 10; i++) r.trackRecentDecision(b(i, `Nr ${i}`));
    expect(r.getRecentDecisions()).toHaveLength(8);
    expect(r.getRecentDecisions()[0].id).toBe(10);
  });

  it("schreibt einen Zeitstempel dazu", async () => {
    const r = await laden();
    r.trackRecentDecision(b(1, "Eins"));
    expect(r.getRecentDecisions()[0].visitedAt).toBeGreaterThan(0);
  });

  it("verträgt kaputten Inhalt und gesperrten Speicher", async () => {
    const r = await laden();
    localStorage.setItem("ratslotse:recent-decisions", "{kein json");
    expect(r.getRecentDecisions()).toEqual([]);
    speicher.kaputt(true);
    expect(() => r.trackRecentDecision(b(1, "Eins"))).not.toThrow();
    expect(r.getRecentDecisions()).toEqual([]);
  });
});

describe("qa-zuletzt — was der Fragen-Screen schon wusste", () => {
  const laden = () => import("./qa-zuletzt");

  it("unterscheidet „noch nie geladen“ von einer gemerkten Liste", async () => {
    // Der ganze Sinn: `null` rechtfertigt Platzhalter, eine Liste nicht.
    const q = await laden();
    expect(q.readExampleQuestions()).toBeNull();
    q.storeExampleQuestions(["Was kostet der Neubau des Stadions?"]);
    expect(q.readExampleQuestions()).toEqual(["Was kostet der Neubau des Stadions?"]);
  });

  it("eine leere Liste zählt wie nie geladen", async () => {
    // Sonst stünde beim nächsten Besuch ein leerer Block statt Platzhaltern.
    const q = await laden();
    q.storeExampleQuestions([]);
    expect(q.readExampleQuestions()).toBeNull();
  });

  it("wirft Nicht-Zeichenketten und Leeres weg", async () => {
    const q = await laden();
    localStorage.setItem("ratslotse:qa-fragen", JSON.stringify(["ok", 42, null, "  "]));
    expect(q.readExampleQuestions()).toEqual(["ok"]);
  });

  it("räumt den Eintrag der alten, erzeugten Vorschläge weg", async () => {
    const q = await laden();
    localStorage.setItem("ratslotse:qa-beispiele", JSON.stringify({ frisch: ["alt"], ts: 1 }));
    q.storeExampleQuestions(["neu?"]);
    expect(localStorage.getItem("ratslotse:qa-beispiele")).toBeNull();
  });

  it("rückt bei jedem Besuch um die gezeigten Fragen weiter", async () => {
    const q = await laden();
    expect(q.readExampleOffset()).toBe(0);
    q.advanceExampleOffset(3);
    q.advanceExampleOffset(2);
    expect(q.readExampleOffset()).toBe(5);
  });

  it("verträgt kaputten Inhalt und gesperrten Speicher", async () => {
    const q = await laden();
    localStorage.setItem("ratslotse:qa-fragen", "{kein json");
    localStorage.setItem("ratslotse:qa-fragen-weiter", "minus eins");
    expect(q.readExampleQuestions()).toBeNull();
    expect(q.readExampleOffset()).toBe(0);
    speicher.kaputt(true);
    expect(() => q.storeExampleQuestions(["a"])).not.toThrow();
    expect(() => q.advanceExampleOffset(3)).not.toThrow();
    expect(q.readExampleOffset()).toBe(0);
  });
});

describe("exampleWindow — welche Fragen gerade dran sind", () => {
  const liste = ["a", "b", "c", "d", "e"];
  const laden = () => import("./qa-zuletzt");

  it("nimmt die nächsten ab dem Zähler", async () => {
    const { exampleWindow } = await laden();
    expect(exampleWindow(liste, 0, 3)).toEqual(["a", "b", "c"]);
    expect(exampleWindow(liste, 3, 2)).toEqual(["d", "e"]);
  });

  it("läuft über das Ende hinweg am Anfang weiter", async () => {
    const { exampleWindow } = await laden();
    expect(exampleWindow(liste, 4, 3)).toEqual(["e", "a", "b"]);
    expect(exampleWindow(liste, 12, 2)).toEqual(["c", "d"]);
  });

  it("zeigt jede Frage einmal, bevor sich eine wiederholt", async () => {
    // Die Zusage aus Tims Wunsch: durchrotieren, nicht würfeln.
    const { exampleWindow } = await laden();
    const zwanzig = Array.from({ length: 20 }, (_, i) => `F${i}`);
    const gesehen: string[] = [];
    for (let zaehler = 0; gesehen.length < 20; zaehler += 2) gesehen.push(...exampleWindow(zwanzig, zaehler, 2));
    expect(new Set(gesehen).size).toBe(20);
  });

  it("nie mehr, als die Liste hat — und nichts bei leerer Liste", async () => {
    const { exampleWindow } = await laden();
    expect(exampleWindow(["a", "b"], 1, 3)).toEqual(["b", "a"]);
    expect(exampleWindow([], 5, 3)).toEqual([]);
    expect(exampleWindow(liste, 0, 0)).toEqual([]);
  });
});

describe("tour-einladung", () => {
  const laden = () => import("./tour-einladung");

  it("kennt nur die beiden erlaubten Stände", async () => {
    const e = await laden();
    expect(e.einladungStand()).toBeNull();
    e.merkeEinladung("offen");
    expect(e.einladungStand()).toBe("offen");
    e.merkeEinladung("erledigt");
    expect(e.einladungStand()).toBe("erledigt");
  });

  it("verwirft einen fremden Wert, statt ihn durchzureichen", async () => {
    const e = await laden();
    localStorage.setItem("ratslotse:tour-einladung", "irgendwas");
    expect(e.einladungStand()).toBeNull();
  });

  it("verträgt gesperrten Speicher in beide Richtungen", async () => {
    const e = await laden();
    speicher.kaputt(true);
    expect(() => e.merkeEinladung("offen")).not.toThrow();
    expect(e.einladungStand()).toBeNull();
  });
});
