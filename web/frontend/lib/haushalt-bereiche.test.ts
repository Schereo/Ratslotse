import { describe, expect, it } from "vitest";
import {
  bereichKanon, bereichKlartext, bereichKurz, bereichSchluessel,
  istSummenzeile, normalisiereBereich,
} from "./haushalt-bereiche";

// Die Bereichsnamen kommen aus dem Haushaltsplan und heißen dort in jedem
// Jahrgang ein bisschen anders: „Personal- und Verwaltungsmanagement" wird zu
// „Personal/Organisation/Digitalisierung/IT", ein Jahrgangspräfix steht davor,
// „u." statt „und". Das Wörterbuch führt sie zusammen.
//
// Der teure Fehler wäre nicht eine Ausnahme, sondern eine STILLE
// Nicht-Zuordnung: Der Bereich taucht dann zweimal auf, einmal unter jedem
// Namen, und beide Balken sind zu kurz.

describe("normalisiereBereich", () => {
  it("wirft das Jahrgangspräfix weg", () => {
    expect(normalisiereBereich("_2026 Verwaltungsführung")).toBe("verwaltungsführung");
  });

  it("vereinheitlicht die Strichsorten", () => {
    // Aus PDFs kommen Halbgeviert- und Geviertstriche statt des Bindestrichs.
    expect(normalisiereBereich("Personal- und Verwaltungsmanagement"))
      .toBe(normalisiereBereich("Personal‐ und Verwaltungsmanagement"));
  });

  it("löst die Abkürzung „u.“ auf", () => {
    expect(normalisiereBereich("Personal- u. Verwaltungsmanagement"))
      .toBe(normalisiereBereich("Personal- und Verwaltungsmanagement"));
  });

  it("zieht Leerraum zusammen und ignoriert Groß- und Kleinschreibung", () => {
    expect(normalisiereBereich("  PERSONAL   und   IT  ")).toBe("personal und it");
  });

  it("fasst ein „u.“ mitten im Wort NICHT an", () => {
    // Sonst würde aus „Kultur.u.Sport" etwas anderes als gemeint — die Regel
    // greift nur auf ein eigenständiges „u.".
    expect(normalisiereBereich("Bau u.Verkehr")).toBe("bau u.verkehr");
  });
});

describe("bereichKanon — bekannte Namen", () => {
  it("führt alle Schreibweisen desselben Bereichs zusammen", () => {
    const namen = [
      "Personal/Organisation/Digitalisierung/IT",
      "Personal- und Verwaltungsmanagement",
      "Personal- u. Verwaltungsmanagement",
      "_2024 Personal- und Verwaltungsmanagement",
    ];
    const schluessel = namen.map((n) => bereichSchluessel(n));
    expect(new Set(schluessel).size).toBe(1);
    expect(schluessel[0]).toBe("personal");
  });

  it("liefert den Anzeigenamen aus dem Wörterbuch, nicht den Rohnamen", () => {
    expect(bereichKanon("Personal- u. Verwaltungsmanagement").name)
      .toBe("Personal/Organisation/Digitalisierung/IT");
  });

  it("kennzeichnet sich als bekannt", () => {
    expect(bereichKanon("Verwaltungsführung").bekannt).toBe(true);
  });

  it("liefert Kurzform und Klartext", () => {
    expect(bereichKurz("Verwaltungsführung")).toBe("Verwaltungsspitze");
    expect(bereichKlartext("Verwaltungsführung")).toContain("Oberbürgermeister");
  });
});

describe("bereichKanon — unbekannte Namen verschwinden NIE stillschweigend", () => {
  it("fällt auf den Rohnamen zurück und sagt das auch", () => {
    const k = bereichKanon("Ganz neuer Bereich 2030");
    expect(k.bekannt).toBe(false);
    expect(k.key).toBeNull();
    expect(k.name).toBe("Ganz neuer Bereich 2030");
  });

  it("kappt die Notkurzform hart, statt einen Kurznamen zu erfinden", () => {
    const k = bereichKanon("Ein ausgesprochen langer neuer Bereichsname ohne Komma");
    expect(k.kurz.length).toBeLessThanOrEqual(20);
    expect(k.kurz.endsWith("…")).toBe(true);
  });

  it("nimmt für die Notkurzform das erste Segment vor Komma oder Schrägstrich", () => {
    expect(bereichKanon("Neues, mit Zusatz").kurz).toBe("Neues");
    expect(bereichKanon("Neues/mit Zusatz").kurz).toBe("Neues");
  });

  it("gibt keinen Klartext her, statt einen zu erfinden", () => {
    expect(bereichKlartext("Ganz neuer Bereich")).toBeNull();
  });

  it("liefert auch für einen leeren Namen ein vollständiges Ergebnis", () => {
    const k = bereichKanon("   ");
    expect(k.bekannt).toBe(false);
    expect(k).toHaveProperty("kurz");
  });
});

describe("istSummenzeile", () => {
  it("erkennt die Summe in allen Schreibweisen", () => {
    for (const n of ["Summe", "SUMME", "  summe  ", "_2026 Summe"]) {
      expect(istSummenzeile(n), n).toBe(true);
    }
  });

  it("hält einen Bereich nicht für eine Summe", () => {
    expect(istSummenzeile("Verwaltungsführung")).toBe(false);
    expect(istSummenzeile("Summe der Erträge")).toBe(false);
  });
});
