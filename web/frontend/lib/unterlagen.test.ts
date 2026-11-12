import { describe, expect, it } from "vitest";
import { ohneDatum, teileListe } from "./unterlagen";

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
  it("kürzt nur unveränderte Stücke und lässt die Änderung ganz", () => {
    const d = kurzerDiff([["=", "Die Ladungsfrist beträgt"], ["-", "zwei Tage."], ["+", "eine Woche."], ["=", lang]]);
    expect(d[0]).toEqual(["=", "Die Ladungsfrist beträgt"]);
    expect(d[1]).toEqual(["-", "zwei Tage."]);
    expect(d[3][1]).toBe("w0 w1 w2 w3 w4 w5 w6 w7 …");
  });
  it("vorn die letzten Wörter, in der Mitte beide Enden", () => {
    const d = kurzerDiff([["=", lang], ["+", "x"], ["=", lang], ["-", "y"]]);
    expect(d[0][1]).toBe("… w22 w23 w24 w25 w26 w27 w28 w29");
    expect(d[2][1]).toBe("w0 w1 w2 w3 w4 w5 w6 w7 … w22 w23 w24 w25 w26 w27 w28 w29");
  });
});
