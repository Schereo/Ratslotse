import { describe, expect, it } from "vitest";
import { GESETZE, herausgeber } from "./gesetze";
import { GLOSSARY } from "./glossary";

// Zwei Nachschlagewerke, die von Hand gepflegt werden. Kein Test kann prüfen,
// ob eine Erklärung STIMMT — prüfbar ist, ob sie vollständig ist und die
// Verweise dorthin zeigen, wo sie hinsollen. Ein Link auf eine falsche Stelle
// ist schlimmer als kein Link: Er behauptet Belegtheit.

describe("GESETZE", () => {
  const eintraege = Object.entries(GESETZE);

  it("ist nicht leer", () => {
    expect(eintraege.length).toBeGreaterThan(0);
  });

  it.each(Object.keys(GESETZE))("%s trägt alle Felder", (schluessel) => {
    const g = GESETZE[schluessel as keyof typeof GESETZE];
    for (const feld of ["kurz", "title", "gesetz", "level", "zusammenfassung", "url"] as const) {
      expect(g[feld], `${schluessel}.${feld}`).toBeTruthy();
    }
  });

  it("verweist ausschließlich auf https", () => {
    for (const [k, g] of eintraege) expect(g.url, k).toMatch(/^https:\/\//);
  });

  it("verweist auf eine AMTLICHE Quelle, passend zur Ebene", () => {
    // Genau das sagt das Fähnchen unter dem Link zu. Zeigt ein Bundesgesetz
    // auf VORIS (oder umgekehrt), steht dort etwas Falsches.
    for (const [k, g] of eintraege) {
      if (g.level === "Bund") expect(g.url, k).toContain("gesetze-im-internet.de");
      else expect(g.url, k).toContain("voris");
    }
  });

  it("kennt nur die beiden Ebenen", () => {
    for (const [k, g] of eintraege) expect(["Bund", "Land"], k).toContain(g.level);
  });

  it("erklärt in ganzen Sätzen", () => {
    for (const [k, g] of eintraege) {
      expect(g.zusammenfassung.length, k).toBeGreaterThan(40);
      expect(g.zusammenfassung.trimEnd(), k).toMatch(/\.$/);
    }
  });
});

describe("herausgeber", () => {
  it("nennt für den Bund das Bundesamt", () => {
    expect(herausgeber({ level: "Bund" } as never)).toContain("gesetze-im-internet.de");
  });

  it("nennt für das Land VORIS", () => {
    expect(herausgeber({ level: "Land" } as never)).toContain("VORIS");
  });

  it("gibt für jede Ebene etwas zurück", () => {
    for (const g of Object.values(GESETZE)) expect(herausgeber(g)).toBeTruthy();
  });
});

describe("GLOSSARY", () => {
  const eintraege = Object.entries(GLOSSARY);

  it("ist nicht leer", () => {
    expect(eintraege.length).toBeGreaterThan(0);
  });

  it("erklärt jeden Begriff in einem ganzen Satz", () => {
    for (const [k, v] of eintraege) {
      expect(v.length, k).toBeGreaterThan(30);
      expect(v.trimEnd(), k).toMatch(/[.…]$/);
    }
  });

  it("erklärt keinen Begriff mit sich selbst als erstem Wort", () => {
    // „Bebauungsplan: Ein Bebauungsplan ist …" hilft niemandem.
    for (const [k, v] of eintraege) {
      expect(v.toLowerCase().startsWith(k.toLowerCase()), `${k}: „${v.slice(0, 40)}…“`).toBe(false);
    }
  });

  it("führt die Grundform als Schlüssel — gematcht wird per Wortanfang", () => {
    for (const k of Object.keys(GLOSSARY)) {
      expect(k.trim(), k).toBe(k);
      expect(k, k).not.toMatch(/\s$/);
    }
  });

  it("führt keinen Begriff doppelt in anderer Schreibweise", () => {
    const klein = Object.keys(GLOSSARY).map((k) => k.toLowerCase());
    expect(new Set(klein).size).toBe(klein.length);
  });
});
