import { describe, expect, it } from "vitest";
import { abfragePfad, bildPfad, delta, fortschritt, halbkreis, kandidatenStatus, koalitionen, mehrheit, nachStimmen, prozent, sitzband, sitzgrenze, standText, uhrzeit, zahl } from "./wahlabend";

describe("Formate", () => {
  it("Zahlen und Prozente auf Deutsch, Lücken als Strich", () => {
    expect(zahl(12345)).toBe("12.345");
    expect(zahl(null)).toBe("–");
    expect(prozent(2.63)).toBe("2,6 %");
    expect(prozent(31.22, 2)).toBe("31,22 %");
    expect(prozent(undefined)).toBe("–");
  });
  it("Delta in Punkten mit Vorzeichen", () => {
    expect(delta(31.2, 19.1)).toBe("+12,1");
    expect(delta(28.9, 32.7)).toBe("−3,8");
    expect(delta(5, 5.01)).toBe("±0,0");
    expect(delta(null, 3)).toBeNull();
  });
  it("Uhrzeit in deutscher Zeit", () => {
    const t = uhrzeit("2026-09-13T18:14:00Z");
    expect(t).toMatch(/^20:14/);
    expect(uhrzeit("kaputt")).toBeNull();
    expect(uhrzeit(null)).toBeNull();
  });
  it("Stand: Uhrzeit am selben Tag, sonst mit Datum", () => {
    const jetzt = new Date("2026-09-13T19:00:00Z");
    expect(standText("2026-09-13T18:14:00Z", jetzt)).toMatch(/^20:14 Uhr$/);
    expect(standText("2026-08-31T10:54:31Z", jetzt)).toMatch(/^31\.08\., 12:54 Uhr$/);
    expect(standText(null)).toBeNull();
  });
  it("Fortschritt gedeckelt", () => {
    expect(fortschritt(11, 133)).toBe(8);
    expect(fortschritt(0, 0)).toBe(0);
    expect(fortschritt(140, 133)).toBe(100);
  });
});

describe("Status einer Kandidatur", () => {
  const k = { votes: 201, elected: null, projected_elected: null, votes_to_seat: 402 };
  it("vor der Auszählung und ohne Personenstimmen sagt er genau das", () => {
    expect(kandidatenStatus(k, "before", false).ton).toBe("unknown");
    expect(kandidatenStatus({ ...k, elected: "direct" }, "counting", true, false).text).toBe("noch nichts ausgezählt");
    expect(kandidatenStatus({ ...k, votes: null }, "counting", false).text).toMatch(/Personenstimmen/);
  });
  it("drin, wackelig, Hochrechnung, knapp, offen, raus", () => {
    expect(kandidatenStatus({ ...k, elected: "list", projected_elected: "list" }, "counting", true)).toEqual({ ton: "seated", text: "drin · über die Liste" });
    expect(kandidatenStatus({ ...k, elected: "direct" }, "counting", true).ton).toBe("shaky");
    expect(kandidatenStatus({ ...k, elected: "direct" }, "complete", true).ton).toBe("seated");
    expect(kandidatenStatus({ ...k, projected_elected: "direct" }, "counting", true).ton).toBe("projected");
    expect(kandidatenStatus({ ...k, votes_to_seat: 120 }, "counting", true)).toEqual({ ton: "close", text: "120 Stimmen bis zum Sitz" });
    expect(kandidatenStatus(k, "counting", true).ton).toBe("open");
    expect(kandidatenStatus({ ...k, votes_to_seat: null }, "counting", true).ton).toBe("out");
  });
});

describe("Sortierung und Sitzband", () => {
  it("nach Stimmen, Lücken hinten in Stimmzettel-Reihenfolge", () => {
    const s = nachStimmen([
      { index: 1, votes: 100 }, { index: 2, votes: null }, { index: 3, votes: 300 }, { index: 4, votes: null },
    ]);
    expect(s.map((p) => p.index)).toEqual([3, 1, 2, 4]);
  });
  it("Sitzband lässt Listen ohne Sitz weg", () => {
    const p = (i: number, seats: number | null) =>
      ({ index: i, slug: `p${i}`, short: `P${i}`, color: "#000", color_dark: "#fff", seats, projected_seats: seats }) as never;
    expect(sitzband([p(1, 3), p(2, 0), p(3, null)], "seats").map((x) => x.n)).toEqual([3]);
  });
  it("Abfragepfad reicht nur gültige Probe-Parameter durch", () => {
    expect(abfragePfad(null, null)).toBe("/wahlabend");
    expect(abfragePfad("2021", "60")).toBe("/wahlabend?probe=2021&counted=60");
    expect(abfragePfad("2021", "x")).toBe("/wahlabend?probe=2021");
  });
});

describe("Mehrheiten und Halbkreis", () => {
  const p = (slug: string, seats: number | null) => ({ slug, seats });
  it("Mehrheit ist mehr als die Hälfte", () => {
    expect(mehrheit(52)).toBe(27);
    expect(mehrheit(50)).toBe(26);
    expect(mehrheit(53)).toBe(27);
  });
  it("nur minimale Bündnisse, nach Partnerzahl und Sitzen sortiert", () => {
    const k = koalitionen([p("a", 17), p("b", 15), p("c", 9), p("d", 5), p("e", 3), p("f", 0), p("g", null)], 52);
    expect(k[0]).toEqual({ slugs: ["a", "b"], seats: 32 });
    // a+b+c hätte die Mehrheit, ist aber nicht minimal (a+b reicht) — fehlt.
    expect(k.find((x) => x.slugs.join() === "a,b,c")).toBeUndefined();
    expect(k).toContainEqual({ slugs: ["a", "c", "d"], seats: 31 });
    expect(k.every((x) => x.seats >= 27 && x.slugs.length <= 3)).toBe(true);
    const zweier = k.filter((x) => x.slugs.length === 2).map((x) => x.seats);
    expect(zweier).toEqual([...zweier].sort((x, y) => y - x));
  });
  it("Alleinmehrheit steht vorn, Listen ohne Sitz fehlen", () => {
    const k = koalitionen([p("a", 30), p("b", 22)], 52);
    expect(k[0]).toEqual({ slugs: ["a"], seats: 30 });
    expect(k.some((x) => x.slugs.includes("b") && x.slugs.length === 1)).toBe(false);
  });
  it("Halbkreis: genau n Plätze, links nach rechts, im Kasten", () => {
    const h = halbkreis(52);
    expect(h).toHaveLength(52);
    expect(h[0].x).toBeLessThan(0.1);
    expect(h[51].x).toBeGreaterThan(1.9);
    expect(h.every((q) => q.x >= 0 && q.x <= 2 && q.y >= 0 && q.y <= 1 && q.r > 0)).toBe(true);
    expect(new Set(h.map((q) => q.reihe)).size).toBe(3);
    expect(halbkreis(0)).toEqual([]);
  });
});

describe("Kandidatenrennen und Bild", () => {
  it("Sitzgrenze ist der schwächste Personensitz, ohne Personensitz keine", () => {
    expect(sitzgrenze([{ votes: 900, elected: "direct" }, { votes: 400, elected: "direct" }, { votes: 380, elected: null }])).toBe(400);
    expect(sitzgrenze([{ votes: 213, elected: "list" }, { votes: 201, elected: null }])).toBeNull();
    expect(sitzgrenze([])).toBeNull();
  });
  it("Bildpfad trägt Feld und Probe-Parameter", () => {
    expect(bildPfad("seats", null, null)).toBe("/wahlabend/bild.png?feld=seats");
    expect(bildPfad("projected_seats", "2021", "60")).toBe("/wahlabend/bild.png?feld=projected_seats&probe=2021&counted=60");
  });
});
