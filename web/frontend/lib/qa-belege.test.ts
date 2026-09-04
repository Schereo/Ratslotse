import { describe, expect, it } from "vitest";
import {
  ANL_EXACT_RE, BELEG_SPLIT_RE, CITE_EXACT_RE, CITE_RE,
  anlagenBuchstabe, anlagenBuchstaben, anlagenNr, citationIds, datenEindeutschen,
} from "./qa-belege";

// Die Beleg-Marker sind eine SYNCHRONE Regel mit dem Backend (council/qa.py,
// _CITE_RE / citation_ids). Laufen beide Seiten auseinander, stimmen
// Fußnoten-Nummerierung und die vom Server gemeldeten `cited` nicht mehr
// überein — die Antwort verweist dann auf den falschen Beschluss.

const treffer = (t: string) => t.match(new RegExp(CITE_RE.source, "g")) ?? [];

describe("CITE_RE — die Beschluss-Klammer", () => {
  it("greift nur, wenn eine Ziffer beginnt", () => {
    // Sonst würde jeder normale Klammertext zur Fußnote.
    expect(treffer("Beschluss [1] und [12, 13]")).toEqual(["[1]", "[12, 13]"]);
    expect(treffer("ein [Hinweis] im Text")).toEqual([]);
    expect(treffer("[siehe 3]")).toEqual([]);
  });

  it("nimmt Text nach der Ziffer mit", () => {
    expect(treffer("[3 Beschluss vom 12.06.]")).toEqual(["[3 Beschluss vom 12.06.]"]);
  });

  it("läuft nicht über eine Zeile hinaus", () => {
    expect(treffer("[1 offen\nnoch offen]")).toEqual([]);
  });

  it("passt exakt, wenn nur die Klammer dasteht", () => {
    expect(CITE_EXACT_RE.test("[1]")).toBe(true);
    expect(CITE_EXACT_RE.test("davor [1]")).toBe(false);
  });
});

describe("citationIds", () => {
  it("liest eine einzelne Nummer", () => {
    expect(citationIds("[7]")).toEqual([7]);
  });

  it("liest eine Liste", () => {
    expect(citationIds("[12, 13, 14]")).toEqual([12, 13, 14]);
    expect(citationIds("[1,2]")).toEqual([1, 2]);
  });

  it("nimmt bei beschriftetem Beleg nur die führende Nummer", () => {
    // „[3 Beschluss 22/0348]" darf nicht auch die 22 und die 348 einsammeln.
    expect(citationIds("[3 Beschluss 22/0348]")).toEqual([3]);
  });

  it("liefert nichts, wenn keine Nummer vorne steht", () => {
    expect(citationIds("[Hinweis]")).toEqual([]);
  });
});

describe("Anlagen-Belege", () => {
  it("anlagenNr liest die Zahl aus [A3]", () => {
    expect(anlagenNr("[A3]")).toBe(3);
    expect(anlagenNr("[A12]")).toBe(12);
  });

  it("ANL_EXACT_RE nimmt höchstens zwei Ziffern", () => {
    expect(ANL_EXACT_RE.test("[A9]")).toBe(true);
    expect(ANL_EXACT_RE.test("[A99]")).toBe(true);
    expect(ANL_EXACT_RE.test("[A100]")).toBe(false);
    expect(ANL_EXACT_RE.test("[A]")).toBe(false);
  });

  it("anlagenBuchstabe zählt a, b, c …", () => {
    expect([0, 1, 2, 25].map(anlagenBuchstabe)).toEqual(["a", "b", "c", "z"]);
  });

  it("läuft nach z wieder um, statt Unsinn zu liefern", () => {
    expect(anlagenBuchstabe(26)).toBe("a");
  });
});

describe("anlagenBuchstaben — nur für Anlagen, die es gibt", () => {
  it("vergibt in der Reihenfolge des Auftauchens", () => {
    const map = anlagenBuchstaben("erst [A2], dann [A1]", [{ nr: 1 }, { nr: 2 }]);
    expect(map.get(2)).toBe("a");
    expect(map.get(1)).toBe("b");
  });

  it("vergibt je Nummer nur einen Buchstaben, auch bei Wiederholung", () => {
    const map = anlagenBuchstaben("[A1] und nochmal [A1]", [{ nr: 1 }]);
    expect(map.size).toBe(1);
    expect(map.get(1)).toBe("a");
  });

  it("schluckt einen halluzinierten Marker ersatzlos", () => {
    // Das Modell erfindet gelegentlich ein „[A9]". Es bekommt keinen
    // Buchstaben — genau wie ungültige [id] serverseitig verworfen werden.
    const map = anlagenBuchstaben("[A1] und [A9]", [{ nr: 1 }]);
    expect(map.has(9)).toBe(false);
    expect(map.size).toBe(1);
  });

  it("zählt ohne `nr` über die Position", () => {
    const map = anlagenBuchstaben("[A2]", [{}, {}]);
    expect(map.get(2)).toBe("a");
  });

  it("verträgt fehlende Anlagen", () => {
    expect(anlagenBuchstaben("[A1]", undefined).size).toBe(0);
    expect(anlagenBuchstaben("[A1]", null).size).toBe(0);
    expect(anlagenBuchstaben("ohne Marker", [{ nr: 1 }]).size).toBe(0);
  });
});

describe("BELEG_SPLIT_RE — beide Sorten in einem Durchgang", () => {
  it("zerlegt den Text und behält die Marker als eigene Stücke", () => {
    const teile = "Text [1] mehr [A2] Ende".split(new RegExp(BELEG_SPLIT_RE.source, "g"));
    expect(teile).toContain("[1]");
    expect(teile).toContain("[A2]");
    expect(teile.join("")).toBe("Text [1] mehr [A2] Ende");
  });
});

describe("datenEindeutschen", () => {
  it("dreht ein ISO-Datum im Fließtext", () => {
    expect(datenEindeutschen("am 2026-06-01 beschlossen")).toBe("am 01.06.2026 beschlossen");
  });

  it("fasst unmögliche Daten nicht an", () => {
    // Eine Aktenzeichen-artige Zahlenfolge soll kein Datum werden.
    expect(datenEindeutschen("2026-13-01")).toBe("2026-13-01");
    expect(datenEindeutschen("2026-00-10")).toBe("2026-00-10");
    expect(datenEindeutschen("2026-06-32")).toBe("2026-06-32");
  });

  it("fasst Teilstücke längerer Zahlenfolgen nicht an", () => {
    expect(datenEindeutschen("12026-06-01")).toBe("12026-06-01");
  });

  it("dreht mehrere Daten in einem Text", () => {
    expect(datenEindeutschen("von 2026-01-01 bis 2026-12-31"))
      .toBe("von 01.01.2026 bis 31.12.2026");
  });

  it("lässt Text ohne Datum in Ruhe", () => {
    expect(datenEindeutschen("kein Datum hier")).toBe("kein Datum hier");
  });
});
