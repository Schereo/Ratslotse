import { describe, expect, it } from "vitest";
import {
  deMonat, deProzent, deZeitraum, istInnenfinanzierung, juengsteZinssaetze,
} from "./haushalt-kredite";

// Die Kredit-Zeilen beantworten „zu welchem Zins?". Zwei Dinge stehen dabei
// auf dem Spiel: ein Zeitraum, der falsch gelesen wird, und eine 0,00 %, die
// wie ein sensationell guter Marktzins aussieht und keiner ist.

const posten = (kind: string, felder: Record<string, unknown> = {}) =>
  ({ kind, heading: "", summary: null, rate_pct: null, ...felder }) as never;

describe("deMonat", () => {
  it("schreibt den Monat aus", () => {
    expect(deMonat("2026-02")).toBe("Februar 2026");
    expect(deMonat("2026-12")).toBe("Dezember 2026");
  });

  it("zeigt für „kein Monat“ einen Strich", () => {
    expect(deMonat(null)).toBe("–");
    expect(deMonat("")).toBe("–");
  });
});

describe("deZeitraum", () => {
  it("nennt einen einzelnen Monat nur einmal", () => {
    // „Februar 2026 bis Februar 2026" liest sich wie ein Fehler.
    expect(deZeitraum("2026-02", "2026-02")).toBe("Februar 2026");
  });

  it("nennt das Jahr innerhalb eines Jahrgangs nur am Ende", () => {
    expect(deZeitraum("2026-02", "2026-06")).toBe("Februar bis Juni 2026");
  });

  it("nennt über die Jahresgrenze BEIDE Jahre", () => {
    // Ohne das läse sich „November bis Februar 2026" als vier Monate im
    // selben Jahr — es sind aber drei über den Jahreswechsel.
    expect(deZeitraum("2025-11", "2026-02")).toBe("November 2025 bis Februar 2026");
  });
});

describe("deProzent", () => {
  it("schreibt deutsch mit zwei Nachkommastellen und Einheit", () => {
    expect(deProzent(3.5)).toBe("3,50 %");
    expect(deProzent(0)).toBe("0,00 %");
    expect(deProzent(3.456)).toBe("3,46 %");
  });

  it("zeigt für „kein Zins“ einen Strich, keine Null", () => {
    // Eine 0,00 % wäre eine Aussage; „kein Zins hinterlegt" ist keine.
    expect(deProzent(null)).toBe("–");
  });
});

describe("juengsteZinssaetze", () => {
  it("nimmt nur Aufnahmen und Prolongationen", () => {
    const d = { rates: [posten("loan"), posten("repayment"), posten("prolongation")] } as never;
    expect(juengsteZinssaetze(d)).toHaveLength(2);
  });

  it("nimmt höchstens n und behält die Reihenfolge", () => {
    const d = { rates: Array.from({ length: 9 }, (_, i) => posten("loan", { heading: `L${i}` })) } as never;
    const aus = juengsteZinssaetze(d, 4);
    expect(aus).toHaveLength(4);
    expect((aus[0] as unknown as { heading: string }).heading).toBe("L0");
  });

  it("verträgt fehlende Daten", () => {
    expect(juengsteZinssaetze(null)).toEqual([]);
    expect(juengsteZinssaetze({} as never)).toEqual([]);
  });
});

describe("istInnenfinanzierung — die 0,00 %, die kein Marktzins ist", () => {
  it("erkennt sie an Zinssatz UND Wortlaut", () => {
    expect(istInnenfinanzierung(posten("loan", {
      rate_pct: 0, heading: "Innenfinanzierung Eigenbetrieb",
    }))).toBe(true);
  });

  it("findet den Hinweis auch in der Zusammenfassung", () => {
    expect(istInnenfinanzierung(posten("loan", {
      rate_pct: 0, heading: "Darlehen", summary: "als Innenfinanzierung geführt",
    }))).toBe(true);
  });

  it("hält eine echte Null-Prozent-Aufnahme NICHT dafür", () => {
    // Sonst verschwände ein tatsächlich zinsloses Darlehen hinter einem
    // Hinweis, der nicht stimmt.
    expect(istInnenfinanzierung(posten("loan", { rate_pct: 0, heading: "Förderdarlehen" })))
      .toBe(false);
  });

  it("hält eine verzinste Innenfinanzierungs-Zeile NICHT dafür", () => {
    expect(istInnenfinanzierung(posten("loan", { rate_pct: 1.5, heading: "Innenfinanzierung" })))
      .toBe(false);
  });

  it("verträgt eine fehlende Zusammenfassung", () => {
    expect(() => istInnenfinanzierung(posten("loan", { rate_pct: 0, heading: "x" }))).not.toThrow();
  });
});
