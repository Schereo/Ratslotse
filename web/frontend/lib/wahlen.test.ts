import { describe, expect, it } from "vitest";
import { ergebnisVermerk, geteilt, gesperrtesTippspiel, istAmtlich, nachJahren, wahlLaut, type Wahlzeile } from "./wahlen";

const z = (slug: string, date: string, focus = false): Wahlzeile => ({
  slug, short_title: slug, title: slug, date, polls_close: `${date}T18:00:00+02:00`,
  kind: "council", status: "live", path: "/wahlabend", summary: null, focus, tipp_path: "", tipp_locked: false, top: [],
  result_status: "vorlaeufig",
});

describe("geteilt", () => {
  it("hebt die Wahl im Fokus heraus", () => {
    const { fokus, weitere } = geteilt([z("a", "2026-09-27"), z("b", "2026-09-13", true), z("c", "2021-09-12")]);
    expect(fokus?.slug).toBe("b");
    expect(weitere.map((x) => x.slug)).toEqual(["a", "c"]);
  });

  it("kommt ohne Fokus aus", () => {
    const { fokus, weitere } = geteilt([z("a", "2026-09-27")]);
    expect(fokus).toBeNull();
    expect(weitere).toHaveLength(1);
  });

  it("der Fokus muss nicht die neueste sein", () => {
    // Am 20.09.: die Stichwahl kommt noch, die Ratswahl ist das jüngste
    // Ergebnis — beide Zeilen sollen richtig stehen.
    const { fokus, weitere } = geteilt([z("stichwahl", "2026-09-27", true), z("ratswahl", "2026-09-13")]);
    expect(fokus?.slug).toBe("stichwahl");
    expect(weitere[0].slug).toBe("ratswahl");
  });
});

describe("nachJahren", () => {
  it("gruppiert und behält die Reihenfolge", () => {
    const gruppen = nachJahren([z("a", "2026-09-27"), z("b", "2026-09-13"), z("c", "2021-09-12")]);
    expect(gruppen.map((g) => g.jahr)).toEqual(["2026", "2021"]);
    expect(gruppen[0].zeilen).toHaveLength(2);
  });
});

describe("gesperrtesTippspiel", () => {
  it("nennt die erste Wahl, für die sich ein Konto lohnt", () => {
    const zeilen = [z("a", "2026-09-27"), { ...z("b", "2026-09-27"), tipp_locked: true }, { ...z("c", "2026-10-01"), tipp_locked: true }];
    expect(gesperrtesTippspiel(zeilen)?.slug).toBe("b");
  });
  it("ist null, wenn nichts gesperrt ist — dann gibt es keinen Grund zum Drängen", () => {
    expect(gesperrtesTippspiel([z("a", "2026-09-27")])).toBeNull();
  });
});

describe("wahlLaut", () => {
  it("folgt allein dem Backend", () => {
    expect(wahlLaut({ prominent: true })).toBe(true);
    expect(wahlLaut({ prominent: false })).toBe(false);
  });
  it("bleibt still, wenn das Feld fehlt — lieber kein Hinweis als einer zur falschen Zeit", () => {
    expect(wahlLaut({})).toBe(false);
    expect(wahlLaut(null)).toBe(false);
    expect(wahlLaut(undefined)).toBe(false);
  });
});

describe("ergebnisVermerk", () => {
  it("sagt amtlich nur, wenn das Backend es sagt", () => {
    expect(istAmtlich("amtlich")).toBe(true);
    expect(istAmtlich("vorlaeufig")).toBe(false);
    expect(istAmtlich(undefined)).toBe(false);
    expect(ergebnisVermerk("amtlich")).toMatch(/amtliche Endergebnis/);
    expect(ergebnisVermerk("amtlich")).not.toMatch(/kein amtliches/i);
  });
  it("nennt ein vorläufiges Ergebnis vorläufig", () => {
    expect(ergebnisVermerk("vorlaeufig")).toMatch(/^Vorläufig/);
    expect(ergebnisVermerk(null)).toMatch(/^Vorläufig/);
  });
});
