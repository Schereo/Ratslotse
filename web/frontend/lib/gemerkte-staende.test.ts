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

  it("unterscheidet „noch nie hier“ von „nichts Frisches“", async () => {
    // Der ganze Sinn: `null` rechtfertigt Platzhalter, ein leeres Array nicht.
    const q = await laden();
    expect(q.leseQaBeispiele()).toBeNull();
    q.merkeQaBeispiele([]);
    expect(q.leseQaBeispiele()).toEqual({ frisch: [] });
  });

  it("gibt gemerkte Vorschläge zurück", async () => {
    const q = await laden();
    q.merkeQaBeispiele(["Wie steht es um das Stadion?"]);
    expect(q.leseQaBeispiele()?.frisch).toEqual(["Wie steht es um das Stadion?"]);
  });

  it("wirft Vorschläge weg, die älter als eine Woche sind", async () => {
    const q = await laden();
    q.merkeQaBeispiele(["alt"]);
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 8 * 24 * 3600 * 1000);
    // Nicht null — „schon da gewesen" bleibt wahr, nur das Frische ist weg.
    expect(q.leseQaBeispiele()).toEqual({ frisch: [] });
    vi.restoreAllMocks();
  });

  it("wirft Nicht-Zeichenketten weg", async () => {
    const q = await laden();
    localStorage.setItem("ratslotse:qa-beispiele", JSON.stringify({ frisch: ["ok", 42, null], ts: Date.now() }));
    expect(q.leseQaBeispiele()?.frisch).toEqual(["ok"]);
  });

  it("verträgt kaputten Inhalt", async () => {
    const q = await laden();
    localStorage.setItem("ratslotse:qa-beispiele", "{kein json");
    expect(q.leseQaBeispiele()).toBeNull();
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
