import { describe, expect, it } from "vitest";
import {
  deDatum, deTagMonat, entscheidung, ergebnisArt, monateZwischen,
  naechsterHaushaltsTermin, rhythmus, strahlRunde, tageZumJahresbeginn, versatzWort,
} from "./haushalt-jahr";

// Aussagen ÜBER die Jahrgänge — „der Entwurf kam siebenmal im Oktober". Sie
// werden gerechnet und nicht geschrieben, genau damit sie sich mitverändern,
// wenn ein Jahrgang dazukommt. Eine falsche Rechnung erzeugt hier einen Satz,
// der plausibel klingt und nicht stimmt: der schlechteste aller Fehler, weil
// niemand ihn nachprüft.

const station = (committee: string, date: string) => ({
  kvonr: 1, date, committee, role: null, is_public: 1, ksinr: 1,
});
const runde = (year: number, stationen: ReturnType<typeof station>[], einbringung?: string) => ({
  year, stationen, einbringung: einbringung ? station("Rat", einbringung) : null,
}) as never;

describe("deDatum / deTagMonat", () => {
  it("schreiben deutsch aus", () => {
    expect(deDatum("2026-02-09")).toBe("9. Februar 2026");
    expect(deTagMonat("2026-02-09")).toBe("9. Februar");
  });

  it("lassen die führende Null weg — „09. Februar“ liest sich falsch", () => {
    expect(deDatum("2026-12-01")).toBe("1. Dezember 2026");
  });

  it("treffen den letzten Monat", () => {
    expect(deTagMonat("2026-12-31")).toBe("31. Dezember");
  });
});

describe("entscheidung — im Rat wird entschieden", () => {
  it("nimmt die LETZTE Station im Rat, nicht die erste", () => {
    // Ein Haushalt kann zweimal in den Rat: erste Lesung, dann Beschluss.
    const r = runde(2026, [
      station("Rat", "2025-10-27"),
      station("Ausschuss für Finanzen und Beteiligungen", "2025-11-20"),
      station("Rat", "2025-12-15"),
    ]);
    expect(entscheidung(r)?.date).toBe("2025-12-15");
  });

  it("fällt auf die letzte Station zurück, wenn der Rat gar nicht vorkommt", () => {
    const r = runde(2026, [station("Verwaltungsausschuss", "2025-12-01")]);
    expect(entscheidung(r)?.date).toBe("2025-12-01");
  });

  it("liefert null ohne Stationen", () => {
    expect(entscheidung(runde(2026, []))).toBeNull();
  });
});

describe("tageZumJahresbeginn", () => {
  it("zählt negativ, wenn VOR dem Haushaltsjahr beschlossen wurde", () => {
    const r = runde(2026, [station("Rat", "2025-12-15")]);
    expect(tageZumJahresbeginn(r)).toBe(-17);
  });

  it("zählt positiv, wenn das Jahr schon lief", () => {
    const r = runde(2026, [station("Rat", "2026-03-01")]);
    expect(tageZumJahresbeginn(r)).toBe(59);
  });

  it("ist am 1. Januar genau null", () => {
    expect(tageZumJahresbeginn(runde(2026, [station("Rat", "2026-01-01")]))).toBe(0);
  });

  it("kippt nicht an der Sommerzeit", () => {
    // Mit lokalen Daten statt UTC läge hier ein Tag daneben — die Umstellung
    // liegt zwischen dem 1. Januar und dem Beschluss.
    expect(tageZumJahresbeginn(runde(2026, [station("Rat", "2026-06-15")]))).toBe(165);
  });

  it("liefert null ohne Beschluss", () => {
    expect(tageZumJahresbeginn(runde(2026, []))).toBeNull();
  });
});

describe("rhythmus — was über alle Jahrgänge gilt", () => {
  const runden = [
    runde(2024, [station("Rat", "2023-12-18")], "2023-10-10"),
    runde(2025, [station("Rat", "2024-12-16")], "2024-10-15"),
    runde(2026, [station("Rat", "2026-02-09")], "2025-11-11"),
  ];

  it("zählt die Jahrgänge", () => {
    expect(rhythmus(runden).jahrgaenge).toBe(3);
  });

  it("sortiert die Einbringungs-Monate nach Häufigkeit", () => {
    const m = rhythmus(runden).entwurfMonate;
    expect(m[0]).toEqual({ monat: 10, count: 2 });
    expect(m[1]).toEqual({ monat: 11, count: 1 });
  });

  it("nennt den frühesten und den spätesten Beschluss", () => {
    const r = rhythmus(runden);
    expect(r.frueheste?.year).toBe(2025);   // 16.12.2024, am weitesten davor
    expect(r.spaeteste?.year).toBe(2026);   // 09.02.2026, im Jahr selbst
  });

  it("zählt, wie oft erst im laufenden Jahr beschlossen wurde", () => {
    expect(rhythmus(runden).imJahrSelbst).toBe(1);
  });

  it("verträgt eine leere Liste, statt zu werfen", () => {
    const r = rhythmus([]);
    expect(r).toMatchObject({ jahrgaenge: 0, entwurfMonate: [], frueheste: null, spaeteste: null, imJahrSelbst: 0 });
  });

  it("überspringt Jahrgänge ohne Einbringung", () => {
    expect(rhythmus([runde(2026, [station("Rat", "2025-12-01")])]).entwurfMonate).toEqual([]);
  });
});

describe("strahlRunde — wo der Zeitstrahl steht", () => {
  const runden = [runde(2024, []), runde(2025, []), runde(2026, [])];

  it("nimmt das Jahr, in dem „heute“ liegt", () => {
    expect(strahlRunde(runden, new Date("2025-06-01"))?.year).toBe(2025);
  });

  it("fällt auf den jüngsten Jahrgang zurück, wenn es zu heute keinen gibt", () => {
    expect(strahlRunde(runden, new Date("2030-01-01"))?.year).toBe(2026);
  });

  it("liefert null ohne Jahrgänge", () => {
    expect(strahlRunde([], new Date("2026-01-01"))).toBeNull();
  });
});

describe("monateZwischen", () => {
  it("zählt über die Jahresgrenze", () => {
    expect(monateZwischen("2025-10-01", "2026-02-01")).toBe(4);
  });

  it("ignoriert den Tag — es sind Monatsgrenzen", () => {
    expect(monateZwischen("2025-10-31", "2025-11-01")).toBe(1);
  });

  it("wird negativ, wenn die Reihenfolge kippt", () => {
    expect(monateZwischen("2026-02-01", "2025-10-01")).toBe(-4);
  });
});

describe("versatzWort", () => {
  it.each([
    [-1, "noch im selben Jahr"],
    [0, "noch im selben Jahr"],
    [1, "im Jahr darauf"],
    [2, "im übernächsten Jahr"],
    [3, "3 Jahre später"],
  ])("%s → %s", (n, wort) => {
    expect(versatzWort(n)).toBe(wort);
  });
});

describe("naechsterHaushaltsTermin — nach GREMIUM, nie nach geratenem Inhalt", () => {
  const sitzung = (committee: string, session_date: string) =>
    ({ ksinr: 1, committee, session_date, session_time: null, location: null });

  it("nimmt den Rat", () => {
    expect(naechsterHaushaltsTermin([sitzung("Sportausschuss", "2026-09-01"), sitzung("Rat", "2026-09-10")])?.committee)
      .toBe("Rat");
  });

  it("nimmt auch den Finanzausschuss", () => {
    expect(naechsterHaushaltsTermin([sitzung("Ausschuss für Finanzen und Beteiligungen", "2026-09-01")]))
      .not.toBeNull();
  });

  it("nimmt den ERSTEN passenden — die Liste kommt schon sortiert", () => {
    expect(naechsterHaushaltsTermin([sitzung("Rat", "2026-09-10"), sitzung("Rat", "2026-10-10")])?.session_date)
      .toBe("2026-09-10");
  });

  it("liefert nichts, wenn kein passendes Gremium tagt", () => {
    expect(naechsterHaushaltsTermin([sitzung("Sportausschuss", "2026-09-01")])).toBeNull();
    expect(naechsterHaushaltsTermin([])).toBeNull();
    expect(naechsterHaushaltsTermin(undefined)).toBeNull();
  });
});

describe("ergebnisArt — die Wortwahl des Ratsinfos auf die Farbe abbilden", () => {
  it.each([
    ["Beschlossen", "accepted"],
    ["geändert beschlossen", "accepted"],
    ["Abgelehnt", "rejected"],
    ["Zur Kenntnis genommen", "noted"],
    ["Zurückgestellt", "postponed"],
    ["abgesetzt", "postponed"],
    ["in den Ausschuss verwiesen", "postponed"],
  ])("„%s“ → %s", (wort, art) => {
    expect(ergebnisArt(wort)).toBe(art);
  });

  it("„abgelehnt“ gewinnt gegen „beschlossen“ im selben Satz", () => {
    // „Der Antrag wurde abgelehnt, der Beschluss der Verwaltung beschlossen"
    // darf nicht grün werden. Die Reihenfolge der Prüfungen ist die Regel.
    expect(ergebnisArt("Antrag abgelehnt, Vorlage beschlossen")).toBe("rejected");
  });

  it("kennt „kein Ergebnis“ als eigenen Zustand", () => {
    expect(ergebnisArt(null)).toBe("no_decision");
    expect(ergebnisArt("")).toBe("no_decision");
    expect(ergebnisArt("Vertagt ohne Aussprache")).toBe("no_decision");
  });
});
