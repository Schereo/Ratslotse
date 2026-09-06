import { describe, expect, it } from "vitest";
import {
  decisionHref, fragenHref, ortHref, personHref, quizHref,
  sessionHref, sitzungHref, themaHref,
} from "./routes";

// Die Adressbauer sind winzig und deshalb leicht zu übersehen — sie sind aber
// die Stelle, an der ein Deep-Link aus einer Mail oder einer Push-Nachricht
// entweder ankommt oder ins Leere zeigt. Zwei Eigenschaften zählen: Der Wert
// muss kodiert sein, und die TOP-Nummer muss VOLLSTÄNDIG mitreisen.

describe("Werte werden kodiert", () => {
  it.each([
    ["personHref", personHref("müller-lüdenscheidt"), "m%C3%BCller"],
    ["themaHref", themaHref("straße & platz"), "%26"],
    ["ortHref", ortHref("a/b"), "a%2Fb"],
    ["quizHref", quizHref("electoral_district:3"), "electoral_district%3A3"],
  ])("%s", (_name, href, erwartet) => {
    expect(href).toContain(erwartet);
  });

  it("ein Slug mit & zerlegt die Adresse nicht in zwei Parameter", () => {
    const href = themaHref("kita & schule");
    expect(href.split("&")).toHaveLength(1);
  });
});

describe("Query statt Pfad", () => {
  // Der ganze (app)-Bereich wird für die native App statisch exportiert.
  // Ein dynamisches Pfadsegment müsste dafür aufgezählt werden — deshalb
  // reist die Kennung als Query-Parameter.
  it.each([
    decisionHref(42),
    personHref("x"),
    themaHref("x"),
    ortHref("x"),
    sessionHref(7),
    sitzungHref(7),
  ])("%s trägt ein ?", (href) => {
    expect(href).toContain("?");
  });

  it("nimmt eine Beschluss-ID als Zahl wie als Zeichenkette", () => {
    expect(decisionHref(42)).toBe(decisionHref("42"));
  });
});

describe("fragenHref", () => {
  it("bleibt ohne Angaben nackt", () => {
    expect(fragenHref()).toBe("/fragen");
    expect(fragenHref({})).toBe("/fragen");
  });

  it("hängt q und share an", () => {
    expect(fragenHref({ q: "Wo steht das Stadion?" }))
      .toBe("/fragen?q=Wo+steht+das+Stadion%3F");
    expect(fragenHref({ q: "a", share: "tok" })).toBe("/fragen?q=a&share=tok");
  });

  it("lässt eine leere Frage weg statt ?q= zu schreiben", () => {
    expect(fragenHref({ q: "" })).toBe("/fragen");
  });
});

describe("TOP-Nummern reisen vollständig mit", () => {
  // DIE Falle: „Ö 6" und „N 6" sind verschiedene Punkte. Wer nur die 6
  // mitschickt, springt in der öffentlichen Sitzung auf den falschen — und
  // bei „Ö 6.1" gegen „6.1" trifft ein Präfix-Vergleich zusätzlich daneben.
  it("nimmt das Präfix mit", () => {
    expect(sessionHref(12, ["Ö 6"])).toContain("top=%C3%96%206");
    expect(sitzungHref(12, ["N 6"])).toContain("top=N%206");
  });

  it("reiht mehrere mit Komma", () => {
    expect(sitzungHref(12, ["Ö 6", "Ö 7.1"])).toContain("top=%C3%96%206%2C%C3%96%207.1");
  });

  it("lässt den Parameter weg, wenn nichts übrig bleibt", () => {
    for (const tops of [undefined, [], ["", "   "]]) {
      expect(sessionHref(12, tops)).toBe("/council?tab=sessions&ksinr=12");
      expect(sitzungHref(12, tops)).toBe("/council/sitzung?ksinr=12");
    }
  });

  it("putzt Leerraum an den Rändern", () => {
    expect(sitzungHref(12, ["  Ö 6  "])).toBe(sitzungHref(12, ["Ö 6"]));
  });
});

describe("sessionHref und sitzungHref führen bewusst woanders hin", () => {
  // `sessionHref` geht in die Sitzungsliste (Konto nötig), `sitzungHref` auf
  // die öffentliche Seite. Ein weitergereichter Link soll ohne Anmeldung
  // lesbar sein — sonst endet „guck mal, was Donnerstag drankommt" im
  // Registrierungsformular.
  it("verschiedene Pfade", () => {
    expect(sessionHref(9).split("?")[0]).toBe("/council");
    expect(sitzungHref(9).split("?")[0]).toBe("/council/sitzung");
  });
});
