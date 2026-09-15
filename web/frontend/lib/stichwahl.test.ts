import { describe, expect, it } from "vitest";
import {
  abfragePfad,
  abstandStimmen,
  bezirkeText,
  chanceText,
  datumLang,
  fuehrend,
  nachStimmen,
  verschiebung,
  vorsprung,
  zeitlage,
  type Stichwahl,
  type StichwahlHochrechnung,
  type StichwahlKandidat,
} from "./stichwahl";

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

// ── Hochrechnung (docs/plan-stichwahl-spannung.md S2) ──────────────────────

const h = (teil: Partial<StichwahlHochrechnung>): StichwahlHochrechnung => ({
  shares: { prange: 51.8, rohr: 48.2 },
  projected_votes: { prange: 44000, rohr: 41000 },
  leader: "prange",
  lead_votes: 3000,
  chance_pct: 71,
  counted_ballot: 41,
  counted_postal: 6,
  open_ballot: 50,
  open_postal: 36,
  decided: false,
  actual_leader: "prange",
  actual_lead_votes: 900,
  open_votes_max: 60000,
  caveats: [],
  ...teil,
});

describe("chanceText", () => {
  it("nennt die Chance des Führenden mit Namen", () => {
    expect(chanceText(h({}), "Ulf Prange")).toBe("Chance: Ulf Prange 71 %");
  });
  it("sagt unter 15 Bezirken, warum es keine gibt", () => {
    expect(chanceText(h({ chance_pct: null, counted_ballot: 9, counted_postal: 1 }), "Ulf Prange")).toMatch(/Erst 10 Bezirke gezählt/);
  });
  it("schweigt, wenn rechnerisch entschieden — dafür gibt es einen eigenen Satz", () => {
    expect(chanceText(h({ decided: true, chance_pct: null }), "Ulf Prange")).toBeNull();
  });
});

describe("bezirkeText", () => {
  it("zählt Urne und Brief getrennt und nennt die Gesamtzahl", () => {
    expect(bezirkeText(h({}))).toBe("nach 47 von 133 Bezirken · Urne 41, Brief 6");
  });
});

describe("bezugsperson (Verlauf)", () => {
  it("zeigt den Anteil dessen, der im ersten Wahlgang vorn lag", async () => {
    const { bezugsperson } = await import("../components/wahlabend/stichwahl-verlauf");
    expect(bezugsperson([k("rohr", 100, 40, 30.5), k("prange", 90, 60, 33.2)])?.slug).toBe("prange");
  });
});

describe("Momente", () => {
  const punkt = (at: string, n: number, prange: number, rohr: number, leader: string | null) => ({
    at,
    reports_received: n,
    shares: { prange: (100 * prange) / (prange + rohr), rohr: (100 * rohr) / (prange + rohr) },
    votes: { prange, rohr },
    projected_shares: {},
    chance_pct: null,
    leader,
  });
  const basis = {
    dataset: "probe",
    phase: "counting",
    election: { slug: "s", title: "", short_title: "", date: "2026-09-27", polls_close: "2026-09-27T16:00:00+00:00", is_runoff: true, presentation_url: "" },
    reports_expected: 133,
    reports_received: 47,
    turnout_pct: null,
    valid_votes: null,
    invalid_ballots: null,
    candidates: [k("prange", 12665, 52.1, 33.2), k("rohr", 11662, 47.9, 30.5)],
    runoff: [],
    elected: null,
    fetched_at: null,
    ok: true,
    error: null,
    notes: [],
    history: [punkt("t1", 35, 9000, 9100, "rohr"), punkt("t2", 47, 12665, 11662, "prange")],
    lead_changes: [{ at: "t2", reports_received: 47, leader: "prange", previous: "rohr" }],
  } as unknown as Stichwahl;

  it("die letzte Meldung: Bezirke und Stimmen seit dem Stand davor", async () => {
    const { letzteMeldung } = await import("./stichwahl");
    expect(letzteMeldung(basis)).toEqual({ at: "t2", bezirke: 12, zuwachs: { prange: 3665, rohr: 2562 } });
    expect(letzteMeldung({ ...basis, history: [basis.history[1]] })?.zuwachs).toEqual({ prange: 12665, rohr: 11662 });
    expect(letzteMeldung({ ...basis, history: [] })).toBeNull();
  });
  it("der Fenstertitel trägt den Stand", async () => {
    const { fensterTitel, letzterWechsel } = await import("./stichwahl");
    expect(fensterTitel({ ...basis, candidates: [k("prange", 12665, 52.1), k("rohr", 11662, 47.9)] })).toBe("prange 52,1 · rohr 47,9 — 47/133 · Stichwahl");
    expect(fensterTitel({ ...basis, phase: "before" })).toBe("Stichwahl · Ratslotse");
    expect(letzterWechsel(basis)?.leader).toBe("prange");
  });
});

describe("Karte", () => {
  it("der Anteil eines Bezirks — erster Wahlgang oder Stichwahl, null ohne Zahlen", async () => {
    const { bezirkAnteil, stichwahlBezirkePfad } = await import("./stichwahl");
    const d = {
      number: 101, name: "x", area: 1, postal: false, counted: false, eligible: 1419, voters: null, valid_votes: null,
      votes: { prange: null, rohr: null }, first_round: { prange: 192, rohr: 258 },
    };
    expect(bezirkAnteil(d, "prange", "first_round")).toBe(42.7);
    expect(bezirkAnteil(d, "prange", "votes")).toBeNull();
    expect(stichwahlBezirkePfad("1", "60")).toBe("/wahlabend/stichwahl/bezirke?probe=1&counted=60");
    expect(stichwahlBezirkePfad(null, "x")).toBe("/wahlabend/stichwahl/bezirke");
  });
});

describe("Karte: Führung und Deckkraft", () => {
  const d = (votes: Record<string, number | null>, first: Record<string, number>, counted: boolean) => ({
    number: 1, name: "x", area: 1, postal: false, counted, eligible: 1, voters: null, valid_votes: null,
    votes, first_round: first,
  });
  it("nennt, wer vorn liegt — gezählt aus der Stichwahl, offen aus dem ersten Wahlgang", async () => {
    const { bezirkFuehrung } = await import("./stichwahl");
    expect(bezirkFuehrung(d({ prange: 300, rohr: 200 }, { prange: 100, rohr: 300 }, true), ["prange", "rohr"])).toEqual({ slug: "prange", share: 60, live: true });
    expect(bezirkFuehrung(d({ prange: null, rohr: null }, { prange: 100, rohr: 300 }, false), ["prange", "rohr"])).toEqual({ slug: "rohr", share: 75, live: false });
    expect(bezirkFuehrung(d({ prange: 5, rohr: 5 }, { prange: 1, rohr: 1 }, true), ["prange", "rohr"])).toBeNull();
  });
  it("die Deckkraft wächst mit dem Vorsprung, offene Bezirke halb so kräftig", async () => {
    const { flaechenAlpha } = await import("./stichwahl");
    expect(flaechenAlpha(50, 70, true)).toBeCloseTo(0.22);
    expect(flaechenAlpha(70, 70, true)).toBeCloseTo(0.9);
    expect(flaechenAlpha(70, 70, false)).toBeCloseTo(0.45);
    expect(flaechenAlpha(52, 52, true)).toBeLessThan(0.6);
  });
});
