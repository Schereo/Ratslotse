import { describe, expect, it } from "vitest";
import { achse, commitLink, grundText, kostenText, modellKurz, rohLink, wertText } from "./benchmarks";

describe("wertText", () => {
  it("rundet Anteile genau einmal auf ganze Prozent", () => {
    expect(wertText(0.6137, "share")).toBe("61 %");
    expect(wertText(1, "share")).toBe("100 %");
  });
  it("sagt bei fehlendem Wert nichts — nie 0 %", () => {
    expect(wertText(null, "share")).toBe("–");
    expect(wertText(undefined, "count")).toBe("–");
  });
  it("kennt Läufe ohne Zahl", () => {
    expect(wertText(null, "none")).toBe("zum Lesen");
  });
  it("Sekunden und Verhältnisse", () => {
    expect(wertText(27, "seconds")).toBe("27 s");
    expect(wertText(0.78, "ratio")).toBe("0,78");
  });
});

describe("kostenText", () => {
  it("unterscheidet null von sehr wenig", () => {
    expect(kostenText(null)).toBe("–");
    expect(kostenText(0.0004)).toBe("< 0,01 $");
    expect(kostenText(1.1)).toBe("1,10 $");
  });
});

describe("grundText", () => {
  const stufe = (k: string) => ({ qa_analysis: "Analyse & Routing" }[k] ?? k);
  it("nennt die Stufe und beide Modelle", () => {
    expect(grundText({ kind: "model", step: "qa_analysis", then: "google/gemini-3.5-flash-lite", now: "openai/gpt-5.6-luna" }, stufe))
      .toBe("Analyse & Routing: heute gpt-5.6-luna, gemessen mit gemini-3.5-flash-lite");
  });
  it("Alter in Tagen", () => {
    expect(grundText({ kind: "age", days: 108 }, stufe)).toBe("zuletzt vor 108 Tagen gemessen");
  });
});

describe("Links", () => {
  it("verlinkt Repo-Pfade, aber keine Server-Dateien", () => {
    expect(rohLink("eval/results/qa/x.json", "https://github.com/o/r")).toBe("https://github.com/o/r/blob/dev/eval/results/qa/x.json");
    expect(rohLink("server:prod:data/eval_gold/ask-a.json", "https://github.com/o/r")).toBeNull();
  });
  it("verlinkt nur echte Commit-Kennungen", () => {
    expect(commitLink("3503ec29d", "https://github.com/o/r")).toBe("https://github.com/o/r/commit/3503ec29d");
    expect(commitLink("unbekannt", "https://github.com/o/r")).toBeNull();
  });
  it("kürzt den Anbieter weg", () => {
    expect(modellKurz("openai/gpt-6-luna")).toBe("gpt-6-luna");
    expect(modellKurz(null)).toBe("–");
  });
});

describe("achse", () => {
  it("schneidet auf den Wertebereich zu, mit Luft", () => {
    const [von, bis] = achse([0.54, 0.57, 0.63], "share");
    expect(von).toBeGreaterThan(0.45);
    expect(von).toBeLessThan(0.54);
    expect(bis).toBeGreaterThan(0.63);
    expect(bis).toBeLessThan(0.72);
  });
  it("hält eine Mindestspanne, damit ein Punkt Unterschied nicht riesig wirkt", () => {
    const [von, bis] = achse([0.61, 0.62], "share");
    expect(bis - von).toBeGreaterThanOrEqual(0.06);
  });
  it("bleibt bei Anteilen zwischen 0 und 1", () => {
    expect(achse([0.98, 1], "share")[1]).toBe(1);
    expect(achse([0, 0.02], "share")[0]).toBe(0);
  });
  it("Zahlen werden nie negativ", () => {
    expect(achse([1, 2], "count")[0]).toBeGreaterThanOrEqual(0);
  });
});
