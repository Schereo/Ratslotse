import { describe, expect, it } from "vitest";
import { abfragePfad, delta, fortschritt, kandidatenStatus, nachStimmen, prozent, sitzband, standText, uhrzeit, zahl } from "./wahlabend";

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
