import { describe, expect, it } from "vitest";
import { ohneDatum, teileListe, angabenWort, aussagenGruppen } from "./unterlagen";

describe("ohneDatum", () => {
  it("nimmt das Datumspräfix ab", () => {
    expect(ohneDatum("2026-10-31 Reduzierung Anzahl beratende Mitglieder")).toBe("Reduzierung Anzahl beratende Mitglieder");
    expect(ohneDatum("2026 11 01. - Antrag Änderung Geschäftsordnung §24")).toBe("Antrag Änderung Geschäftsordnung §24");
    expect(ohneDatum("20241025 DIE GRÜNEN Verweisungsantrag")).toBe("DIE GRÜNEN Verweisungsantrag");
    expect(ohneDatum("251107 Dringlichkeitsantrag GRÜNEN")).toBe("Dringlichkeitsantrag GRÜNEN");
  });
  it("lässt Labels ohne Datum und reine Daten stehen", () => {
    expect(ohneDatum("Änderungsantrag CDU Geschäftsordnung Rat 2.11.26")).toBe("Änderungsantrag CDU Geschäftsordnung Rat 2.11.26");
    expect(ohneDatum("2026-10-31")).toBe("2026-10-31");
  });
});

describe("teileListe", () => {
  it("Lesestoff vorn, Belegmaterial und Protokolle getrennt", () => {
    const t = teileListe([
      { kind: "template", doc_type: "template", label: "Vorlage" },
      { kind: "attachment", doc_type: "amendment", label: "Änderungsantrag" },
      { kind: "attachment", doc_type: "plan", label: "Lageplan" },
      { kind: "protocol", label: "Protokoll Rat" },
      { kind: "attachment", label: "ohne Art" },
    ]);
    expect(t.lesestoff.map((d) => d.label)).toEqual(["Vorlage", "Änderungsantrag"]);
    expect(t.beleg.map((d) => d.label)).toEqual(["Lageplan", "ohne Art"]);
    expect(t.protokolle).toHaveLength(1);
  });
});

import { kurzerDiff } from "./unterlagen";

describe("kurzerDiff", () => {
  const lang = Array.from({ length: 30 }, (_, i) => `w${i}`).join(" ");
  it("ohne Satzgrenze: nur unveränderte Stücke kürzen, die Änderung bleibt ganz", () => {
    const d = kurzerDiff([["=", "Die Ladungsfrist beträgt"], ["-", "zwei Tage."], ["+", "eine Woche."], ["=", lang]]);
    expect(d[0]).toEqual(["=", "Die Ladungsfrist beträgt"]);
    expect(d[1]).toEqual(["-", "zwei Tage."]);
    expect(d[3][1]).toBe("w0 w1 w2 w3 w4 w5 w6 w7 …");
  });
  it("ohne Satzgrenze: vorn die letzten Wörter, in der Mitte beide Enden", () => {
    const d = kurzerDiff([["=", lang], ["+", "x"], ["=", lang], ["-", "y"]]);
    expect(d[0][1]).toBe("… w22 w23 w24 w25 w26 w27 w28 w29");
    expect(d[2][1]).toBe("w0 w1 w2 w3 w4 w5 w6 w7 … w22 w23 w24 w25 w26 w27 w28 w29");
  });
  it("hinten bis zum Satzende — der Satz nach der Änderung bricht nicht mitten ab", () => {
    // Volt, GO-Änderung Rat 02.11.2026: früher endete es bei „sechs Stunden …"
    const d = kurzerDiff([["=", "Die Ladungsfrist beträgt"], ["-", "zwei Tage."], ["+", "eine Woche."],
      ["=", "In dringenden Fällen kann sie auf sechs Stunden verkürzt werden. Die Ladung erfolgt schriftlich oder elektronisch."]]);
    expect(d[3][1]).toBe("In dringenden Fällen kann sie auf sechs Stunden verkürzt werden. …");
  });
  it("ein Datum ist kein Satzende", () => {
    // VBN-Tarif, Beschluss 9487: Der Rest endete bei „… des ZVBN am 10. …".
    const d = kurzerDiff([["-", "alt."], ["+", "neu."],
      ["=", "In der Verbandsversammlung des ZVBN am 10. September 2026 wird entsprechend abgestimmt. Danach folgt ein weiterer Satz."]]);
    expect(d[2][1]).toBe("In der Verbandsversammlung des ZVBN am 10. September 2026 wird entsprechend abgestimmt. …");
  });
  it("vorn ab dem letzten Satzende", () => {
    const d = kurzerDiff([["=", "Der erste Satz steht hier. Die Frist beträgt"], ["-", "zwei"], ["+", "sieben"], ["=", "Tage."]]);
    expect(d[0][1]).toBe("… Die Frist beträgt");
    expect(d[3][1]).toBe("Tage.");
  });
});

describe("aussagenGruppen", () => {
  const a = (kind: string, text = kind) => ({ kind, text });

  it("fasst gleiche Arten zusammen und nennt die Zwischenzeile einmal", () => {
    const g = aussagenGruppen([a("plain"), a("not_included", "x"), a("not_included", "y")]);
    expect(g.map((x) => [x.kind, x.label, x.aussagen.length])).toEqual([
      ["plain", null, 1], ["not_included", "Nicht Teil des Beschlusses", 2]]);
  });

  it("Kosten ohne Zwischenzeile, die Deckung darunter mit", () => {
    expect(aussagenGruppen([a("items"), a("items"), a("coverage")]).map((x) => x.label)).toEqual([null, "Deckung"]);
  });

  it("Termine tragen ihre Zeile nur neben offenen Punkten", () => {
    expect(aussagenGruppen([a("dates"), a("dates")]).map((x) => x.label)).toEqual([null]);
    expect(aussagenGruppen([a("dates"), a("open")]).map((x) => x.label)).toEqual(["Termine", "Noch offen"]);
    expect(aussagenGruppen([a("open")]).map((x) => x.label)).toEqual(["Noch offen"]);
  });

  it("leer bleibt leer", () => {
    expect(aussagenGruppen([])).toEqual([]);
  });
});

describe("angabenWort", () => {
  it("zählt in Einzahl und Mehrzahl", () => {
    expect(angabenWort(1)).toBe("1 Angabe");
    expect(angabenWort(5)).toBe("5 Angaben");
  });
});
