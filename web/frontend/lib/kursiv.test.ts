import { describe, expect, it } from "vitest";
import { teileKursiv } from "./kursiv";

const kursiv = (t: string) => teileKursiv(t).filter((x) => x.kursiv).map((x) => x.text);
const zusammen = (t: string) => teileKursiv(t).map((x) => x.text).join("");

describe("teileKursiv", () => {
  it("erkennt Kursivschrift, wie GPT-6 Luna sie setzt", () => {
    const t = "Im *Ergebnishaushalt* werden Produkte und im *Finanzhaushalt* Investitionen geführt.";
    expect(kursiv(t)).toEqual(["Ergebnishaushalt", "Finanzhaushalt"]);
    expect(zusammen(t)).toBe(t.replaceAll("*", ""));
  });

  it("nimmt mehrere Wörter und Satzzeichen danach", () => {
    expect(kursiv("das *Konzept Berlin*, beschlossen")).toEqual(["Konzept Berlin"]);
    expect(kursiv("(*Plan*)")).toEqual(["Plan"]);
  });

  it("lässt Gendersternchen, Rechenzeichen und Aufzählungen stehen", () => {
    for (const t of ["Mitarbeiter*innen und Bürger*innen", "3 * 4 = 12", "* erster Punkt", "a * b * c"]) {
      expect(kursiv(t)).toEqual([]);
      expect(zusammen(t)).toBe(t);
    }
  });

  it("lässt ein offenes Sternchen beim Streamen stehen", () => {
    expect(kursiv("im *Ergebnis")).toEqual([]);
    expect(zusammen("im *Ergebnis")).toBe("im *Ergebnis");
  });

  it("fasst Fettschrift nicht an (die zerlegt AntwortText vorher)", () => {
    expect(kursiv("**fett**")).toEqual([]);
  });
});
