import { describe, expect, it } from "vitest";
import { anteilIn, bezirkeIn, deckkraft, farbe, fuehrungText, lageSatz, wahlParam, werNachSlug, type Wahlkarte, type WahlkarteBezirk } from "./wahlkarte";

// Die Anzeige-Regeln der Wahl-Ebene: Deckkraft aus dem Vorsprung, die
// Bezirke eines Ortsbereichs (größter Anteil zuerst) und der Satz, der sagt,
// wenn ein Bezirk nur zum Teil im Ortsbereich liegt.

function bezirk(number: number, places: [string, number][], extra: Partial<WahlkarteBezirk> = {}): WahlkarteBezirk {
  return {
    number, name: `Bezirk ${number}`, area: 2, counted: true, leader: "spd", runner_up: "gruene", margin_pct: 5,
    turnout_pct: 60, valid_votes: 1000, places: places.map(([name, share]) => ({ name, share })), parties: [], ...extra,
  };
}

const daten = {
  election: { slug: "ratswahl-2026", label: "Ratswahl", kind: "council", date: "2026-09-13" },
  elections: [
    { slug: "ratswahl-2026", label: "Ratswahl", kind: "council", date: "2026-09-13" },
    { slug: "ob-2026", label: "OB-Wahl", kind: "mayor", date: "2026-09-13" },
  ],
  phase: "complete",
  contestants: [
    { slug: "spd", short: "SPD", name: "SPD", color: "#e3000f", color_dark: "#ff4d57" },
    { slug: "cdu", short: "CDU", name: "CDU", color: "#1a1a1a", color_dark: "#9ca3af" },
  ],
  postal_share_pct: 32.2, total: 3, counted: 3, wins: [], ties: 0, place: null, areas: [],
  districts: [
    bezirk(203, [["Haarenesch", 0.7], ["Innenstadt", 0.3]]),
    bezirk(204, [["Eversten", 0.44], ["Innenstadt", 0.29], ["Dobbenviertel", 0.27]]),
    bezirk(101, [["Bürgerfelde", 1]]),
  ],
} as Wahlkarte;

describe("deckkraft", () => {
  it("wächst mit dem Vorsprung und ist ab 20 Punkten satt", () => {
    expect(deckkraft(null)).toBe(0);
    expect(deckkraft(0)).toBeCloseTo(0.15);
    expect(deckkraft(10)).toBeGreaterThan(deckkraft(2));
    expect(deckkraft(20)).toBeCloseTo(0.75);
    expect(deckkraft(40)).toBeCloseTo(0.75);
  });
});

describe("farbe", () => {
  it("nimmt im Dunkeln die helle Fassung — CDU-Schwarz wäre dort eine Wand", () => {
    const wer = werNachSlug(daten);
    expect(farbe(wer.get("cdu"), false)).toBe("#1a1a1a");
    expect(farbe(wer.get("cdu"), true)).toBe("#9ca3af");
    expect(farbe(undefined, false)).toMatch(/^#/);
  });
});

describe("bezirkeIn", () => {
  it("findet alle Bezirke, die den Ortsbereich berühren, größter Anteil zuerst", () => {
    expect(bezirkeIn(daten, "Innenstadt").map((d) => d.number)).toEqual([203, 204]);
    expect(bezirkeIn(daten, "Bürgerfelde").map((d) => d.number)).toEqual([101]);
    expect(bezirkeIn(daten, "Atlantis")).toEqual([]);
    expect(anteilIn(daten.districts[1], "Innenstadt")).toBeCloseTo(0.29);
  });
});

describe("lageSatz", () => {
  it("nennt den Anteil, wenn ein Bezirk nur zum Teil im Ortsbereich liegt", () => {
    expect(lageSatz(daten.districts[1], "Innenstadt")).toBe("Liegt nur zu 29 % in Innenstadt, sonst in Eversten und Dobbenviertel.");
    expect(lageSatz(daten.districts[2], "Bürgerfelde")).toBeNull();
  });
  it("nennt auf der Stadt-Stufe die Ortsbereiche, wenn es mehrere sind", () => {
    expect(lageSatz(daten.districts[1], null)).toBe("Liegt in Eversten, Innenstadt und Dobbenviertel.");
    expect(lageSatz(daten.districts[2], null)).toBeNull();
  });
});

describe("fuehrungText", () => {
  it("unterscheidet vorn, Gleichstand und nicht gezählt", () => {
    const wer = werNachSlug(daten);
    expect(fuehrungText(daten.districts[0], wer)).toBe("vorn: SPD");
    expect(fuehrungText(bezirk(400, [], { leader: null, margin_pct: 0 }), wer)).toBe("Gleichstand");
    expect(fuehrungText(bezirk(1, [], { counted: false, leader: null }), wer)).toBe("noch nicht gezählt");
  });
});

describe("wahlParam", () => {
  it("lässt die Vorgabe aus der Adresse heraus", () => {
    expect(wahlParam("ratswahl-2026", daten)).toBeNull();
    expect(wahlParam("ob-2026", daten)).toBe("ob-2026");
    expect(wahlParam(null, daten)).toBeNull();
  });
});
