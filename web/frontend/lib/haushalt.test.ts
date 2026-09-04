import { describe, expect, it } from "vitest";
import { amount, deMio, haushaltUrl, herkunftVon, jahreSortiert, mio } from "./haushalt";

describe("herkunftVon — die Funktion aus dem Vorfall", () => {
  // #970: Die Antwortform war geschlossen und trug `provenance` nicht mehr.
  // Die Haushalts-Seite blieb daraufhin LEER statt nur ohne Beleg. Die Regel
  // steht seither im Docstring: Eine fehlende Karte ist kein Fehler.
  const daten = { provenance: { "7": { document: "Haushaltsplan 2026" } as never } };

  it("findet über die Zahl wie über die Zeichenkette", () => {
    expect(herkunftVon(daten, 7)).toBe(daten.provenance["7"]);
  });

  it("liefert null statt zu werfen, wenn die Karte gar nicht dabei ist", () => {
    for (const d of [undefined, null, {}, { provenance: undefined }]) {
      expect(herkunftVon(d as never, 7)).toBeNull();
    }
  });

  it("liefert null für eine unbekannte oder fehlende ID", () => {
    expect(herkunftVon(daten, 999)).toBeNull();
    expect(herkunftVon(daten, null)).toBeNull();
    expect(herkunftVon(daten, undefined)).toBeNull();
  });

  it("verwechselt die ID 0 nicht mit „keine ID“", () => {
    const mitNull = { provenance: { "0": { document: "x" } as never } };
    expect(herkunftVon(mitNull, 0)).not.toBeNull();
  });
});

describe("amount — die Einheit passt zur Größenordnung", () => {
  // Die Produktebene spannt vier Größenordnungen. Alles starr in Mio.
  // anzugeben macht aus dem halben Bestand „0,0 Mio. €".
  it.each([
    [58_600_000, "58,6", "Mio. €"],
    [1_000_000, "1,0", "Mio. €"],
    [999_999, "1.000", "Tsd. €"],
    [10_000, "10", "Tsd. €"],
    [9_999, "9.999", "€"],
    [4_206, "4.206", "€"],
    [0, "0", "€"],
  ])("%s €", (wert, zahl, einheit) => {
    expect(amount(wert)).toEqual({ value: zahl, unit: einheit });
  });

  it("wählt die Einheit nach dem BETRAG, nicht nach dem Vorzeichen", () => {
    expect(amount(-58_600_000)).toEqual({ value: "-58,6", unit: "Mio. €" });
    expect(amount(-4_206)).toEqual({ value: "-4.206", unit: "€" });
  });

  it("zeigt für „kein Wert“ einen Strich und keine Einheit", () => {
    // Eine Einheit ohne Zahl liest sich wie „0 €" — sichtbar falsch wäre
    // schlimmer als knapp.
    expect(amount(null)).toEqual({ value: "—", unit: "" });
    expect(amount(undefined)).toEqual({ value: "—", unit: "" });
  });

  it("gruppiert deutsch mit Punkt", () => {
    expect(amount(1_234_567).value).toBe("1,2");
    expect(amount(123_456).value).toBe("123");
    expect(amount(1_234).value).toBe("1.234");
  });
});

describe("mio und deMio", () => {
  it("rundet auf eine Nachkommastelle", () => {
    expect(mio(283_140_000)).toBe(283.1);
    expect(mio(283_160_000)).toBe(283.2);
    expect(mio(49_999)).toBe(0);
  });

  it("reicht „kein Wert“ durch", () => {
    expect(mio(null)).toBeNull();
    expect(mio(undefined)).toBeNull();
    expect(deMio(null)).toBe("—");
  });

  it("schreibt deutsch, immer mit einer Nachkommastelle", () => {
    expect(deMio(283.1)).toBe("283,1");
    expect(deMio(1000)).toBe("1.000,0");
    expect(deMio(0)).toBe("0,0");
  });
});

describe("haushaltUrl", () => {
  it("reiht die Felder mit Komma", () => {
    expect(haushaltUrl(["years", "reserves"])).toBe("/council/budget?felder=years,reserves");
  });

  it("hängt die Teilhaushalts-Auswahl nur an, wenn sie gesetzt ist", () => {
    expect(haushaltUrl(["years"])).not.toContain("sub_budget_item");
    expect(haushaltUrl(["years"], "keine")).toContain("sub_budget_item=keine");
    // „20" ist ein gültiger Wert und darf nicht als leer durchfallen.
    expect(haushaltUrl(["years"], "20")).toContain("sub_budget_item=20");
  });
});

describe("jahreSortiert", () => {
  it("sortiert numerisch, nicht alphabetisch", () => {
    // Der Fehler, gegen den das steht: Objekt-Schlüssel sind Zeichenketten,
    // und „2009" < „999" wäre alphabetisch falsch herum.
    const daten = { years: { "2026": {}, "999": {}, "2009": {} } as never };
    expect(jahreSortiert(daten)).toEqual([999, 2009, 2026]);
  });

  it("verträgt einen leeren Jahrgang", () => {
    expect(jahreSortiert({ years: {} } as never)).toEqual([]);
  });
});
