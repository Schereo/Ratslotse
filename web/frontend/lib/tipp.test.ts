import { describe, expect, it } from "vitest";
import {
  beteiligungAus,
  fehltText,
  kandidaturenSatz,
  probePfad,
  prozentText,
  punkteText,
  punkteZeile,
  regelSatz,
  rangDeltaText,
  rangPfeil,
  restOb,
  restObText,
  restObTon,
  restSitze,
  restSitzeText,
  restSitzeTon,
  summeOb,
  summeSitze,
  tippSegmente,
  uhrzeitKurz,
} from "./tipp";
import type { TippPartei } from "./tipp";

function partei(slug: string, seats_previous: number | null, color = "#123456"): TippPartei {
  return { slug, short: slug, name: slug, color, color_dark: color, seats_previous } as TippPartei;
}

describe("fehltText", () => {
  it("nennt die fehlenden Sitze im Singular und Plural", () => {
    expect(fehltText(12, false, 100)).toBe("Noch 12 Sitze verteilen");
    expect(fehltText(1, false, 100)).toBe("Noch 1 Sitz verteilen");
  });

  it("nennt auch die Überzahl", () => {
    expect(fehltText(-3, false, 100)).toBe("3 Sitze zu viel");
    expect(fehltText(-1, false, 100)).toBe("1 Sitz zu viel");
  });

  it("meldet die OB-Prozente erst, wenn die Sitze stimmen", () => {
    // Rest 5 UND OB über 100: Die Sitze stehen oben, also kommen sie zuerst.
    expect(fehltText(5, true, -2)).toBe("Noch 5 Sitze verteilen");
    expect(fehltText(0, true, -2)).toBe("OB-Prozente über 100 %");
    // Rundungstoleranz wie im Backend (bis 100,5 %) und ein zugeklappter
    // OB-Block blockieren nicht.
    expect(fehltText(0, true, -0.4)).toBeNull();
    expect(fehltText(0, false, -50)).toBeNull();
  });

  it("gibt null zurück, wenn alles passt — dann darf abgegeben werden", () => {
    expect(fehltText(0, true, 12)).toBeNull();
    expect(fehltText(0, false, 100)).toBeNull();
  });
});

describe("Rest der Sitzverteilung", () => {
  it("Text und Ton an den drei Fällen", () => {
    expect(restSitzeText(0, 52)).toBe("52 von 52 — passt");
    expect(restSitzeTon(0)).toBe("ok");
    expect(restSitzeText(3, 52)).toBe("Noch 3 Sitze");
    expect(restSitzeText(1, 52)).toBe("Noch 1 Sitz");
    expect(restSitzeTon(3)).toBe("warn");
    expect(restSitzeText(-2, 52)).toBe("2 Sitze zu viel");
    expect(restSitzeText(-1, 52)).toBe("1 Sitz zu viel");
  });

  it("restSitze rechnet gegen die Gesamtzahl", () => {
    expect(restSitze({ a: 20, b: 20 }, 52)).toBe(12);
    expect(restSitze({ a: 52 }, 52)).toBe(0);
    expect(restSitze({ a: 60 }, 52)).toBe(-8);
  });
});

describe("tippSegmente", () => {
  const parteien = [partei("spd", 12, "#e3000f"), partei("cdu", 12, "#1a1a1a")];

  it("je Liste mit Sitzen ein Segment, Breite in Prozent der Gesamtzahl", () => {
    const segs = tippSegmente({ spd: 13, cdu: 0 }, parteien, 52);
    expect(segs).toEqual([{ slug: "spd", farbe: "#e3000f", breite: "25%" }]);
  });

  it("deckelt bei Überschreitung — die Leiste läuft nie über den Rahmen", () => {
    const segs = tippSegmente({ spd: 40, cdu: 40 }, parteien, 52);
    const gesamtbreite = segs.reduce((s, x) => s + parseFloat(x.breite), 0);
    expect(gesamtbreite).toBeCloseTo(100, 5);
  });
});

describe("OB-Prozente", () => {
  it("Summe, Rest, Text und Ton", () => {
    expect(summeOb({ a: 30, b: 70 })).toBe(100);
    expect(restOb({ a: 30, b: 70 })).toBe(0);
    expect(restObText(0)).toBe("100,0 % — passt");
    expect(restObTon(0)).toBe("ok");
    expect(restObText(5.5)).toBe("Noch 5,5 %");
    expect(restObText(-2)).toBe("2,0 % zu viel");
    // Unter 100 % ist gültig — der Server verlangt keine Summe (§ „ohne
    // Summenzwang"), er lehnt nur eine Summe über 100 % ab. Blockiert werden
    // darf deshalb nur der echte Fehlerfall, nicht „noch nicht ganz voll".
    expect(restObTon(3)).toBe("ok");
    expect(restObTon(0)).toBe("ok");
    expect(restObTon(-0.5)).toBe("ok");
    expect(restObTon(-2)).toBe("warn");
  });

  it("rundet Fließkomma-Reste auf eine Nachkommastelle", () => {
    expect(restOb({ a: 33.3, b: 33.3, c: 33.3 })).toBeCloseTo(0.1, 5);
  });
});

describe("Rang-Pfeil", () => {
  it("auf/ab/gleich, null ohne Vergleich oder ohne eigenen Rang", () => {
    expect(rangPfeil(2, 5)).toEqual({ richtung: "auf", um: 3 });
    expect(rangPfeil(5, 2)).toEqual({ richtung: "ab", um: 3 });
    expect(rangPfeil(3, 3)).toEqual({ richtung: "gleich", um: 0 });
    expect(rangPfeil(null, 3)).toBeNull();
    expect(rangPfeil(3, null)).toBeNull();
  });

  it("als Satz", () => {
    expect(rangDeltaText({ richtung: "auf", um: 3 })).toBe("3 Plätze vorgerückt");
    expect(rangDeltaText({ richtung: "auf", um: 1 })).toBe("1 Platz vorgerückt");
    expect(rangDeltaText({ richtung: "ab", um: 2 })).toBe("2 Plätze zurückgefallen");
    expect(rangDeltaText({ richtung: "gleich", um: 0 })).toBe("unverändert");
    expect(rangDeltaText(null)).toBe("");
  });
});

describe("Kleinkram", () => {
  it("punkteText mit Singular", () => {
    expect(punkteText(1)).toBe("1 Punkt");
    expect(punkteText(5)).toBe("5 Punkte");
    expect(punkteText(0)).toBe("0 Punkte");
  });

  it("uhrzeitKurz in deutscher Zeit", () => {
    expect(uhrzeitKurz("2026-09-13T18:02:00Z")).toMatch(/^20:02/);
    expect(uhrzeitKurz(null)).toBeNull();
    expect(uhrzeitKurz("kaputt")).toBeNull();
  });
});

describe("probePfad", () => {
  it("lässt den Pfad in Ruhe, wenn keine Generalprobe läuft", () => {
    expect(probePfad("/tipp/me", null, null)).toBe("/tipp/me");
  });

  it("hängt probe und counted an", () => {
    expect(probePfad("/tipp/me", "2021", "90")).toBe("/tipp/me?probe=2021&counted=90");
  });

  it("verwirft ein counted, das keine Zahl ist — der Server antwortete sonst mit 422", () => {
    expect(probePfad("/tipp/me", "2021", "viele")).toBe("/tipp/me?probe=2021");
  });
});

describe("Wahlbeteiligung und Prozentwahl (19.09.2026)", () => {
  it("beteiligungAus: leer heißt nicht getippt, Komma zählt wie Punkt, geklemmt auf 0–100", () => {
    expect(beteiligungAus("")).toBeNull();
    expect(beteiligungAus("   ")).toBeNull();
    expect(beteiligungAus("abc")).toBeNull();
    expect(beteiligungAus("45,5")).toBe(45.5);
    expect(beteiligungAus("45.25")).toBe(45.3);
    expect(beteiligungAus("120")).toBe(100);
    expect(beteiligungAus("-3")).toBe(0);
  });

  it("kandidaturenSatz reiht die Namen mit „und“", () => {
    expect(kandidaturenSatz([])).toBe("");
    expect(kandidaturenSatz([{ name: "Ulf Prange" }])).toBe("Ulf Prange");
    expect(kandidaturenSatz([{ name: "Jascha Rohr" }, { name: "Ulf Prange" }])).toBe("Jascha Rohr und Ulf Prange");
    expect(kandidaturenSatz([{ name: "A" }, { name: "B" }, { name: "C" }])).toBe("A, B und C");
  });

  it("prozentText ist deutsch mit einer Nachkommastelle, Strich ohne Wert", () => {
    expect(prozentText(63.46)).toBe("63,5 %");
    expect(prozentText(52)).toBe("52,0 %");
    expect(prozentText(null)).toBe("–");
  });

  it("punkteZeile nennt Sitze nur bei einer Sitzwahl", () => {
    const score = { total: 15, seat_points: 5, mayor_points: 6, turnout_points: 3, exact_lists: 1, deviation: 2, pct_deviation: 1.5 };
    expect(punkteZeile(score, true)).toBe("Sitze 5 · OB-Bonus 6 · Wahlbeteiligung 3 · 1 Listen richtig getippt");
    expect(punkteZeile(score, false)).toBe("Kandidaturen 6 · Wahlbeteiligung 3");
    expect(punkteZeile(null, false)).toBe("");
  });

  it("regelSatz unterscheidet die Wahlart", () => {
    expect(regelSatz(true)).toMatch(/Je Liste/);
    expect(regelSatz(false)).toMatch(/Je Kandidatur/);
    expect(regelSatz(false)).toMatch(/Wahlbeteiligung/);
  });
});
