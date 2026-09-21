import { describe, expect, it } from "vitest";

import { begriffeIn } from "./glossar-treffer";

/** Geprüft wird gegen das ECHTE Glossar (`lib/glossary.ts`, erzeugt aus
 *  `kern/glossar.py`) — eine erfundene Wortliste prüfte die Fixture. */
describe("begriffeIn", () => {
  it("findet die Fachwörter in Reihenfolge des Auftauchens", () => {
    expect(begriffeIn("Der Haushalt und die Umschuldung."))
      .toEqual(["Haushalt", "Umschuldung"]);
  });

  it("findet Beugungen — „Bebauungsplans“ ist derselbe Begriff", () => {
    expect(begriffeIn("Der Entwurf des Bebauungsplans liegt aus."))
      .toContain("Bebauungsplan");
  });

  it("nimmt das längere Wort: „Doppelhaushalt“ ist nicht „Haushalt“", () => {
    expect(begriffeIn("Der Doppelhaushalt 2026/27.")).toEqual(["Doppelhaushalt"]);
  });

  it("nennt denselben Begriff nur einmal", () => {
    expect(begriffeIn("Haushalt hin, Haushalt her.")).toEqual(["Haushalt"]);
  });

  it("deckelt, statt eine ganze Antwort durchzurechnen", () => {
    const viel = "Haushalt Umschuldung Bebauungsplan Satzung Fraktion Ausschuss";
    expect(begriffeIn(viel, 2)).toHaveLength(2);
  });

  it("findet nichts in einem Text ohne Fachwort", () => {
    expect(begriffeIn("Die Treppe zeigt die Rückzahlung.")).toEqual([]);
    expect(begriffeIn("")).toEqual([]);
  });
});
