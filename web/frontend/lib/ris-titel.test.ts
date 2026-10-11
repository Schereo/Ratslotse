import { describe, expect, it } from "vitest";
import { ohneRisErgebnis } from "./ris-titel";

describe("ohneRisErgebnis", () => {
  it.each([
    ["Jahresabschluss 2022 der Stadt Oldenburg (Kernverwaltung) - Beschluss Beschluss: ungeändert beschlossen",
      "Jahresabschluss 2022 der Stadt Oldenburg (Kernverwaltung)"],
    ["Bericht der Verwaltung Beschluss: zur Kenntnis genommen", "Bericht der Verwaltung"],
    ["Radweg am Damm -Beschluss Beschluss: geändert beschlossen", "Radweg am Damm"],
    ["Radweg am Damm - Beschluss - Beschluss: ungeändert beschlossen", "Radweg am Damm"],
    ["Sanierungsplan Sportstätten - Beschlussantrag Beschluss: abgelehnt", "Sanierungsplan Sportstätten - Beschlussantrag"],
    ["Feststellung der Beschlussfähigkeit Beschluss: ungeändert beschlossen", "Feststellung der Beschlussfähigkeit"],
    ["Hafen Beschluss: ungeändert beschlossen Abstimmung: Ja: 11, Nein: 0, Enthaltung: 0", "Hafen"],
  ])("%s", (roh, erwartet) => {
    expect(ohneRisErgebnis(roh)).toBe(erwartet);
  });

  it("lässt Titel ohne Anhang in Ruhe", () => {
    expect(ohneRisErgebnis("Beschlussfähigkeit und Tagesordnung")).toBe("Beschlussfähigkeit und Tagesordnung");
    expect(ohneRisErgebnis("Bebauungsplan Nr. 123 - Beschluss")).toBe("Bebauungsplan Nr. 123");
  });

  it("gibt nie einen leeren Titel zurück", () => {
    expect(ohneRisErgebnis("Beschluss: abgelehnt")).toBe("Beschluss: abgelehnt");
  });
});
