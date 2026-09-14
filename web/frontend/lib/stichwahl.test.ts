import { describe, expect, it } from "vitest";
import { abfragePfad, abstandStimmen, datumLang, fuehrend, nachStimmen, verschiebung, vorsprung, zeitlage, type StichwahlKandidat } from "./stichwahl";

// Der Typ kommt aus dem Vertrag, nicht aus einer Handschrift daneben: Ein
// neues Pflichtfeld in der Antwort soll hier auffallen (web/frontend/CLAUDE.md).
const k = (slug: string, votes: number | null, share: number | null, vorher: number | null = null): StichwahlKandidat =>
  ({ slug, name: slug, party: "", votes, share_pct: share, first_round_pct: vorher, color: "", color_dark: "",
     nominated_by: "", independent: false, supported_by: [], note_source: "" });

describe("nachStimmen", () => {
  it("sortiert absteigend", () => {
    expect(nachStimmen([k("a", 10, 25), k("b", 30, 75)]).map((x) => x.slug)).toEqual(["b", "a"]);
  });
  it("nimmt vor der Auszählung den ersten Wahlgang", () => {
    expect(nachStimmen([k("a", null, null, 30.5), k("b", null, null, 33.2)]).map((x) => x.slug)).toEqual(["b", "a"]);
  });
  it("lässt die Reihenfolge des Stimmzettels, wenn es gar nichts zu sortieren gibt", () => {
    expect(nachStimmen([k("a", null, null), k("b", null, null)]).map((x) => x.slug)).toEqual(["a", "b"]);
  });
});

describe("fuehrend", () => {
  it("nennt die Person mit den meisten Stimmen", () => {
    expect(fuehrend([k("a", 10, 25), k("b", 30, 75)])).toBe("b");
  });
  it("behauptet bei Gleichstand nichts — dann entscheidet das Los", () => {
    expect(fuehrend([k("a", 30, 50), k("b", 30, 50)])).toBeNull();
  });
  it("behauptet nichts, solange nichts ausgezählt ist", () => {
    expect(fuehrend([k("a", null, null), k("b", 0, null)])).toBeNull();
  });
});

describe("Abstände", () => {
  it("vorsprung rechnet in Prozentpunkten", () => {
    expect(vorsprung([k("a", 10, 47.94), k("b", 30, 52.06)])).toBe(4.12);
  });
  it("vorsprung ist null, solange nur eine Zahl da ist", () => {
    expect(vorsprung([k("a", 10, 100), k("b", null, null)])).toBeNull();
  });
  it("abstandStimmen nennt die Zahl, um die es geht", () => {
    expect(abstandStimmen([k("a", 25850, 47.9), k("b", 28075, 52.1)])).toBe(2225);
  });
});

describe("verschiebung", () => {
  it("vergleicht mit dem ersten Wahlgang", () => {
    expect(verschiebung(k("a", 100, 52.06, 33.16))).toBe(18.9);
  });
  it("ist null ohne Vergleichswert", () => {
    expect(verschiebung(k("a", 100, 52.06, null))).toBeNull();
  });
});

describe("zeitlage", () => {
  const schluss = "2026-09-27T18:00:00+02:00";
  it("zählt die Tage bis zum Wahlsonntag", () => {
    expect(zeitlage(schluss, new Date("2026-09-21T09:00:00+02:00"))).toMatchObject({ phase: "vorher", tage: 6 });
  });
  it("sagt am Wahltag „Heute“", () => {
    expect(zeitlage(schluss, new Date("2026-09-27T09:00:00+02:00")).kicker).toBe("Heute ab 18 Uhr");
  });
  it("läuft ab 18 Uhr", () => {
    expect(zeitlage(schluss, new Date("2026-09-27T18:00:01+02:00")).phase).toBe("laeuft");
  });
  it("hält einen unbrauchbaren Termin aus, statt NaN zu zeigen", () => {
    expect(zeitlage("keine Zeit").phase).toBe("laeuft");
  });
});

describe("Kleinkram", () => {
  it("datumLang schreibt den Monat aus", () => {
    expect(datumLang("2026-09-27")).toBe("27. September 2026");
  });
  it("abfragePfad hängt nur an, was da ist", () => {
    expect(abfragePfad(null, null)).toBe("/wahlabend/stichwahl");
    expect(abfragePfad("ja", "40")).toBe("/wahlabend/stichwahl?probe=ja&counted=40");
    expect(abfragePfad("ja", "abc")).toBe("/wahlabend/stichwahl?probe=ja");
  });
});
