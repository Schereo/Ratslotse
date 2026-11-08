import { describe, expect, it } from "vitest";
import { stimme, vielfaeltigeAuswahl } from "./debatten";

const b = (party: string | null, speaker: string | null = null) => ({ party, speaker });

describe("vielfaeltigeAuswahl", () => {
  it("nimmt erst jede Fraktion einmal, nicht fünfmal dieselbe", () => {
    const liste = [b("SPD"), b("SPD"), b("SPD"), b("CDU"), b("SPD"), b("Grüne"), b(null, "Oberbürgermeister")];
    const auswahl = vielfaeltigeAuswahl(liste, 4);
    expect(auswahl.map(stimme)).toEqual(["spd", "cdu", "grüne", "oberbürgermeister"]);
  });

  it("füllt mit den übrigen auf, wenn es weniger Stimmen als Plätze gibt", () => {
    const liste = [b("SPD"), b("SPD"), b("CDU"), b("SPD")];
    expect(vielfaeltigeAuswahl(liste, 3)).toEqual([liste[0], liste[1], liste[2]]);
  });

  it("behält die ursprüngliche Reihenfolge", () => {
    const liste = [b("SPD"), b("SPD"), b("CDU")];
    expect(vielfaeltigeAuswahl(liste, 2)).toEqual([liste[0], liste[2]]);
  });

  it("gibt kurze Listen unverändert zurück", () => {
    const liste = [b("SPD"), b("SPD")];
    expect(vielfaeltigeAuswahl(liste, 5)).toBe(liste);
  });
});
