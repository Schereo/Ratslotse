import { describe, expect, it } from "vitest";
import { absatzVorschau } from "./haushalt-beteiligungen";

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
