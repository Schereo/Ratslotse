import { describe, expect, it } from "vitest";
import {
  absatzVorschau, euroVoll, planTitel, quartalsjahrVon, stichtagText,
  type BeteiligungsDaten,
} from "./haushalt-beteiligungen";

describe("absatzVorschau", () => {
  it("klappt einen kurzen Text nicht ein, auch wenn er Absätze hat", () => {
    // Der Auftrag der Großleitstelle: 385 Zeichen. Bis 24.09.2026 stand
    // davon eine PDF-Zeile da und der Rest hinter „Ganzen Wortlaut zeigen".
    const text = "Hauptzweck ist das Betreiben der Großleitstelle.\n".repeat(7).trim();
    expect(absatzVorschau(text)).toEqual({ kopf: text, rest: "" });
  });

  it("zeigt bei langem Text den ersten Absatz", () => {
    const erster = "Erster Absatz mit Inhalt.";
    const text = `${erster}\n${"Weiterer Text, der lang ist. ".repeat(30)}`;
    const { kopf, rest } = absatzVorschau(text);
    expect(kopf).toBe(erster);
    expect(rest.length).toBeGreaterThan(600);
  });

  it("schneidet langen Text ohne Absatz am Satzende", () => {
    const text = "Ein Satz, der etwas länger ist als nötig. ".repeat(20).trim();
    const { kopf, rest } = absatzVorschau(text);
    expect(kopf.endsWith(".")).toBe(true);
    expect(`${kopf} ${rest}`).toBe(text);
  });
});

describe("Quartalsberichte der Beteiligungen", () => {
  it("nennt den Plan nur dann „Geänderter Plan“, wenn der Bericht ihn so nennt", () => {
    expect(planTitel("adjusted")).toBe("Geänderter Plan");
    expect(planTitel("original")).toBe("Plan");
    expect(planTitel(null)).toBe("Plan");
  });

  it("schreibt Stichtag und Betrag deutsch, im vollen Euro", () => {
    expect(stichtagText("2025-12-31")).toBe("31.12.2025");
    expect(euroVoll(-25_429_193)).toBe("-25.429.193 €");
    expect(euroVoll(627_510)).toBe("627.510 €");
  });

  it("findet das Jahr eines Unternehmens und nichts ohne Stationen", () => {
    const station = { as_of: "2025-12-31", quarter: 4, plan: -1, plan_kind: "original",
      forecast: -2, plan_other: null, plan_other_kind: null, rounded: false,
      conflict_note: null, statement: null, template_number: "26/0124", herkunft_id: null };
    const daten = { forecasts: [
      { company: "klinikum", year: 2025, basis: "result", stations: [station],
        actual: null, actual_note: null },
      { company: "otm", year: 2025, basis: "result", stations: [],
        actual: null, actual_note: null },
    ] } as unknown as BeteiligungsDaten;
    expect(quartalsjahrVon(daten, "klinikum")?.year).toBe(2025);
    expect(quartalsjahrVon(daten, "otm")).toBeNull();
    expect(quartalsjahrVon(daten, "weh")).toBeNull();
    expect(quartalsjahrVon(null, "klinikum")).toBeNull();
  });
});
