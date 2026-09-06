import { describe, expect, it } from "vitest";
import { belegziel, belegzieleAlle, vorgangVerb, zielText, zielart } from "./haushalt-dokumente";

// Der Beleg-Apparat: Jede Zahl auf den Haushalts-Seiten führt zu ihrem Papier.
// Zwei Fallen stecken darin, und beide erzeugen keinen Fehler, sondern eine
// falsche Behauptung — die schlimmste Sorte auf einer Seite, die Belege
// verspricht.

const dok = (year: number, url: string, title = `Dokument ${year}`) =>
  ({ year, url, title, note: null, page: null });

describe("zielart — der Linktext muss die Wahrheit sagen", () => {
  it.each([
    ["https://buergerinfo.oldenburg.de/getfile.php?id=1", "dokument"],
    ["https://example.org/plan.pdf", "dokument"],
    ["https://example.org/daten.CSV", "datensatz"],
    ["https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=1", "vorlage"],
    ["https://buergerinfo.oldenburg.de/to0040.php?x=1", "vorlage"],
    ["https://buergerinfo.oldenburg.de/suche", "ris"],
    ["https://oldenburg.de/statistik", "webseite"],
  ])("%s → %s", (url, art) => {
    expect(zielart(url)).toBe(art);
  });

  it("hält eine Vorlagen-Seite NICHT für ein Dokument", () => {
    // Sie listet ihre Anlagen; „Dokument öffnen" wäre eine falsche Zusage.
    expect(zielText("https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=1"))
      .toContain("Vorlage");
  });

  it("erkennt getfile.php auch ohne Endung als Datei", () => {
    expect(zielart("https://buergerinfo.oldenburg.de/getfile.php?id=9")).toBe("dokument");
  });

  it("gibt für jede Art einen Text", () => {
    for (const url of ["x.pdf", "x.csv", "vo0050.php", "buergerinfo.oldenburg.de/x", "x.de"]) {
      expect(zielText(url).length).toBeGreaterThan(5);
    }
  });
});

describe("vorgangVerb", () => {
  it.each([
    ["accepted", "beschlossen"],
    ["rejected", "abgelehnt"],
    ["postponed", "vertagt"],
    ["noted", "zur Kenntnis genommen"],
  ])("%s → %s", (o, v) => expect(vorgangVerb(o)).toBe(v));

  it("bleibt bei Unbekanntem beim neutralen Wort", () => {
    // „behandelt" behauptet nichts über den Ausgang.
    expect(vorgangVerb(null)).toBe("behandelt");
    expect(vorgangVerb("irgendwas")).toBe("behandelt");
  });
});

describe("belegziel", () => {
  const dokumente = {
    plan: [dok(2024, "a.pdf"), dok(2026, "b.pdf"), dok(2025, "c.pdf")],
  } as never;

  it("nimmt das Dokument des gezeigten Jahres", () => {
    const z = belegziel(dokumente, "plan" as never, 2025);
    expect(z?.dokument.url).toBe("c.pdf");
    expect(z?.abweichend).toBe(false);
  });

  it("fällt auf das JÜNGSTE zurück und schreibt das an", () => {
    // Ohne `abweichend` stünde ein Beleg von 2026 unter einer Zahl von 2023 —
    // die Anzeige muss den Jahrgang dann nennen.
    const z = belegziel(dokumente, "plan" as never, 2023);
    expect(z?.dokument.url).toBe("b.pdf");
    expect(z?.budget_year).toBe(2026);
    expect(z?.abweichend).toBe(true);
  });

  it("nimmt ohne Jahresangabe ebenfalls das jüngste und meldet es als abweichend", () => {
    const z = belegziel(dokumente, "plan" as never, null);
    expect(z?.dokument.url).toBe("b.pdf");
    expect(z?.abweichend).toBe(true);
  });

  it("liefert null, wenn es zu dieser Quelle gar nichts gibt", () => {
    expect(belegziel(dokumente, "gibtesnicht" as never, 2026)).toBeNull();
    expect(belegziel(undefined, "plan" as never, 2026)).toBeNull();
    expect(belegziel({ plan: [] } as never, "plan" as never, 2026)).toBeNull();
  });

  it("zählt DATEIEN, nicht Fundstellen", () => {
    // Dieselbe Anlage kommt dreimal (Abfallbehandlung, Abfallsammlung,
    // Straßenreinigung). „Alle 3 Dokumente" führte sonst zu einem
    // Verzeichnis mit EINEM Eintrag.
    const dreimal = { gebuehren: [dok(2026, "same.pdf", "Abfallbehandlung"),
                                  dok(2026, "same.pdf", "Abfallsammlung"),
                                  dok(2026, "same.pdf", "Straßenreinigung")] } as never;
    expect(belegziel(dreimal, "gebuehren" as never, 2026)?.weitere).toBe(0);
  });

  it("zählt echte weitere Dateien desselben Jahrgangs mit", () => {
    const zwei = { plan: [dok(2026, "a.pdf"), dok(2026, "b.pdf")] } as never;
    expect(belegziel(zwei, "plan" as never, 2026)?.weitere).toBe(1);
  });
});

describe("belegzieleAlle — je Adresse einmal", () => {
  it("führt dieselbe Datei nur einmal auf", () => {
    const dreimal = { gebuehren: [dok(2026, "same.pdf", "Abfallbehandlung"),
                                  dok(2026, "same.pdf", "Abfallsammlung")] } as never;
    expect(belegzieleAlle(dreimal, "gebuehren" as never, 2026)).toHaveLength(1);
  });

  it("führt verschiedene Dateien desselben Jahrgangs alle auf", () => {
    const zwei = { plan: [dok(2026, "a.pdf"), dok(2026, "b.pdf")] } as never;
    expect(belegzieleAlle(zwei, "plan" as never, 2026)).toHaveLength(2);
  });

  it("liefert eine leere Liste, wo es nichts gibt", () => {
    expect(belegzieleAlle(undefined, "plan" as never, 2026)).toEqual([]);
  });
});
