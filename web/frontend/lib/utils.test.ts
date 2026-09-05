import { describe, expect, it } from "vitest";
import { cn, formatDate, formatDateTime, pfad, relativerTag, wochentagKurz } from "./utils";

describe("formatDate", () => {
  it("dreht ISO auf deutsche Schreibweise", () => {
    expect(formatDate("2026-07-24")).toBe("24.07.2026");
  });

  it("schneidet den Zeitanteil ab", () => {
    // Ohne das Abschneiden ergäbe die Zerlegung an „-" das hier:
    // „24T09:21:18.07.2026". Der Fehler stand einmal live.
    expect(formatDate("2026-07-24T09:21:18")).toBe("24.07.2026");
  });

  it("reicht Unlesbares unverändert durch, statt Unsinn zu bauen", () => {
    expect(formatDate("demnächst")).toBe("demnächst");
    expect(formatDate("")).toBe("");
  });
});

describe("formatDateTime", () => {
  it("hängt die Uhrzeit an, wenn eine da ist", () => {
    expect(formatDateTime("2026-07-24T09:21:18")).toBe("24.07.2026, 09:21");
  });

  it("ist ohne Zeitanteil identisch zu formatDate", () => {
    expect(formatDateTime("2026-07-24")).toBe(formatDate("2026-07-24"));
  });
});

describe("wochentagKurz", () => {
  // Bewusst NICHT auf „Do." mit Punkt festgenagelt: Die Kurzform kommt aus
  // der Sprachdatenbank der Laufzeit (ICU/CLDR), und die hat den Punkt bei
  // deutschen Kurz-Wochentagen inzwischen fallen lassen — gemessen unter ICU
  // 78: „Do". Ein Test auf die genaue Schreibweise ginge beim nächsten
  // Node-Sprung kaputt, ohne dass jemand einen Fehler gemacht hätte.
  // Geprüft wird deshalb, worauf sich die Oberfläche wirklich verlässt.
  it("nennt den richtigen Tag, deutsch und kurz", () => {
    expect(wochentagKurz("2026-09-03")).toMatch(/^Do\.?$/);   // ein Donnerstag
    expect(wochentagKurz("2026-09-06")).toMatch(/^So\.?$/);
  });

  it("bleibt kurz — die Zeile im Sitzungstab hat keinen Platz", () => {
    for (const tag of ["2026-09-01", "2026-09-02", "2026-09-03",
                       "2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07"]) {
      expect(wochentagKurz(tag).length).toBeLessThanOrEqual(3);
    }
  });

  it("liefert für jeden Wochentag etwas anderes", () => {
    const woche = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
                   "2026-09-05", "2026-09-06", "2026-09-07"].map(wochentagKurz);
    expect(new Set(woche).size).toBe(7);
  });

  it("verträgt einen Zeitanteil und liefert sonst nichts", () => {
    expect(wochentagKurz("2026-09-03T18:00:00")).toBe(wochentagKurz("2026-09-03"));
    expect(wochentagKurz("2026-9-3")).toBe("");
    expect(wochentagKurz("kein Datum")).toBe("");
    expect(wochentagKurz("")).toBe("");
  });

  it("kippt nicht an der Zeitzone", () => {
    // Mit „T00:00" statt „T12:00" läge der Tag westlich von UTC einen
    // Kalendertag früher. Deshalb steht Mittag in der Funktion.
    expect(wochentagKurz("2026-01-01")).toBe(wochentagKurz("2026-01-01"));
    expect(wochentagKurz("2026-01-01")).toMatch(/^Do\.?$/);
  });
});

describe("relativerTag", () => {
  const heute = new Date("2026-09-03T10:00:00");

  it.each([
    ["2026-09-03", "heute"],
    ["2026-09-04", "morgen"],
    ["2026-09-02", "gestern"],
  ])("%s → %s", (tag, erwartet) => {
    expect(relativerTag(tag, heute)).toBe(erwartet);
  });

  it("schweigt, wenn der Tag weiter weg ist", () => {
    expect(relativerTag("2026-09-05", heute)).toBeNull();
    expect(relativerTag("2026-09-01", heute)).toBeNull();
  });

  it("rechnet über Monats- und Jahresgrenzen", () => {
    expect(relativerTag("2026-10-01", new Date("2026-09-30T10:00:00"))).toBe("morgen");
    expect(relativerTag("2027-01-01", new Date("2026-12-31T10:00:00"))).toBe("morgen");
    expect(relativerTag("2026-12-31", new Date("2027-01-01T10:00:00"))).toBe("gestern");
  });

  it("schweigt ohne „heute“ — der statische Export hätte sonst das Build-Datum", () => {
    expect(relativerTag("2026-09-03", null)).toBeNull();
  });

  it("schweigt bei unlesbarem Datum", () => {
    expect(relativerTag("demnächst", heute)).toBeNull();
  });
});

describe("pfad — die eine Stelle für den Schluss-Schrägstrich", () => {
  // `next.config.mjs` setzt für den App-Export `trailingSlash: true`. In der
  // App heißt der Pfad „/council/", im Web „/council". Jeder exakte Vergleich
  // war damit in der App blind — der Sitzungen-Tab leuchtete nie.
  it.each([
    ["/council/", "/council"],
    ["/council", "/council"],
    ["/haushalt/schulden/", "/haushalt/schulden"],
    ["/", "/"],
    ["", "/"],
  ])("%s → %s", (ein, aus) => {
    expect(pfad(ein)).toBe(aus);
  });

  it("verträgt null und undefined", () => {
    expect(pfad(null)).toBe("/");
    expect(pfad(undefined)).toBe("/");
  });

  it("räumt auch mehrere Schrägstriche ab", () => {
    expect(pfad("/council///")).toBe("/council");
  });
});

describe("cn", () => {
  it("fügt Klassen zusammen", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("lässt die spätere Tailwind-Klasse gewinnen", () => {
    // Der Sinn von twMerge: Sonst stünden beide da und die Reihenfolge im
    // Stylesheet entschiede — also nicht die Aufrufstelle.
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("wirft Falsches weg", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });

  it("nimmt Bedingungen als Objekt", () => {
    expect(cn("a", { b: true, c: false })).toBe("a b");
  });
});
