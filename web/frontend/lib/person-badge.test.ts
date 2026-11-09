import { describe, expect, it } from "vitest";

import {
  hasNameSignal, namensWoerterDavor, parteiAusListenpunkt, perPartei, perVollname, personBadgeLabel,
} from "./person-badge";

describe("personBadgeLabel", () => {
  it("nennt beratende Mitglieder auf Deutsch, nicht mit dem Datenbankwert", () => {
    // Tims Befund 01.11.2026: Das Badge stand als „advisory" in Lottis Antwort.
    expect(personBadgeLabel({ aktiv: true, art: "advisory", party: null })).toBe("beratend");
  });

  it("zeigt Ehemalige als „ehem.“ und Ratsleute mit Parteikürzel", () => {
    expect(personBadgeLabel({ aktiv: false, art: "advisory", party: null })).toBe("ehem.");
    expect(personBadgeLabel({ aktiv: true, art: "council", party: "BÜNDNIS 90/DIE GRÜNEN" })).toBe("Grüne");
    expect(personBadgeLabel({ aktiv: true, art: "city", party: null })).toBe("Stadt");
  });
});

/** Prüft die erste Fundstelle von `name` in `text`. */
function signal(text: string, name: string, firstName: string | null = null): boolean {
  const start = text.indexOf(name);
  if (start < 0) throw new Error(`${name} steht nicht in „${text}“`);
  return hasNameSignal(text, start, start + name.length, firstName);
}

describe("hasNameSignal — Nachnamen, die gewöhnliche Wörter sind", () => {
  // Alle vier stammen aus gespeicherten Antworten auf dev (01.11.2026).
  it.each([
    ["Danke der Nachfrage! Ich bin bereit.", "Danke", "andré"],
    ["Laut Protokoll gab es Streit über die Prioritäten.", "Streit", "tim"],
    ["am ehemaligen Combi-Standort Bremer Heerstraße soll", "Bremer", "michael"],
    ["zum Schlossgarten oder zum Eversten Holz betreffen andere Orte", "Holz", "angela"],
  ])("„%s“ ist kein Name", (text, name, firstName) => {
    expect(signal(text, name, firstName)).toBe(false);
  });

  it("lässt ein Satzzeichen nicht als Nachbarschaft durchgehen", () => {
    expect(signal("Er sagte. Krogmann ist zuständig.", "Krogmann", "juergen")).toBe(false);
    expect(signal("**Sander**, zunächst für die Piraten", "Sander", "andreas")).toBe(false);
  });
});

describe("hasNameSignal — Zeichen, die einen Namen ausweisen", () => {
  it("Vorname davor, auch ein zweiter Vorname und ein Akzent", () => {
    expect(signal("Ulf Prange hielt dagegen.", "Prange", "ulf")).toBe(true);
    expect(signal("Jonas Christopher Höpken begrüßte das.", "Höpken", "jonas christopher")).toBe(true);
    expect(signal("Das sagt André Danke.", "Danke", "andré")).toBe(true);
  });

  it("Anrede oder Amt davor, auch zusammengesetzt", () => {
    expect(signal("Darauf antwortete Herr Adler knapp.", "Adler", "hans-henning")).toBe(true);
    expect(signal("Baak und Dr. Kreft-Kohlhage", "Kreft-Kohlhage", "brigitte")).toBe(true);
    expect(signal("SPD-Ratsmitglied Prange hielt dagegen.", "Prange", "ulf")).toBe(true);
    expect(signal("Laut Protokoll äußerte Einwohnerin Pieper Bedenken.", "Pieper", "juergen")).toBe(true);
    expect(signal("Ratsherr van Ellen wünschte sich mehr.", "Ellen", "thorsten")).toBe(true);
  });

  it("ein Verb des Sagens direkt daneben", () => {
    expect(signal("Sprenger sagte, die Verwaltung prüfe das.", "Sprenger", "robert")).toBe(true);
    expect(signal("Im März kritisierte Höpken die Lösung.", "Höpken", "jonas christopher")).toBe(true);
    expect(signal("Später kritisierten Skiba und andere das.", "Skiba", "ben")).toBe(true);
    expect(signal("Im April sprach sich Prange für den Neubau aus.", "Prange", "ulf")).toBe(true);
  });

  it("eine Parteiklammer dahinter", () => {
    expect(signal("Prange (SPD) hielt dagegen.", "Prange", "ulf")).toBe(true);
    expect(signal("Wenzel (Grüne-Fraktion) hielt dagegen.", "Wenzel", null)).toBe(true);
  });

  it("ohne solches Zeichen bleibt auch ein echter Name ohne Badge", () => {
    // Der Preis der Regel, bewusst: lieber kein Badge als ein geratenes.
    expect(signal("während Höpken die Containerlösung kritisierte", "Höpken", "jonas christopher")).toBe(false);
  });
});

describe("Namensvettern: was der Text sonst noch belegt (09.11.2026)", () => {
  const ruth = [
    { name: "Ruth Regina Drügemöller", party: "Grüne", art: "council" },
    { name: "Ruth Drügemöller", party: "Grüne", art: "council" },
  ];
  it("der volle Name passt genau auf einen Eintrag", () => {
    const text = "Laut Protokoll sagte Tim Harms zu; Ruth Regina Drügemöller wollte zustimmen.";
    const pos = text.indexOf("Drügemöller");
    const davor = namensWoerterDavor(text, pos);
    expect(davor).toEqual(["Ruth", "Regina"]);
    expect(perVollname(ruth, davor, "Drügemöller")?.name).toBe("Ruth Regina Drügemöller");
    expect(perVollname(ruth, ["Ruth"], "Drügemöller")?.name).toBe("Ruth Drügemöller");
    expect(perVollname(ruth, ["Anna"], "Drügemöller")).toBeNull();
  });
  it("die Partei aus dem Listenpunkt trennt Namensvettern", () => {
    expect(parteiAusListenpunkt("**AfD** stellte sich gegen … Paul erklärte, er werde sich enthalten.")).toBe("AfD");
    expect(parteiAusListenpunkt("**Kosten** stiegen")).toBeNull();
    const paul = [
      { name: "Andreas Paul", party: "AfD", art: "council" },
      { name: "Anna Paul", party: null, art: "advisory" },
      { name: "Matthias Paul", party: null, art: "city" },
    ];
    expect(perPartei(paul, "AfD")?.name).toBe("Andreas Paul");
    expect(perPartei(paul, "SPD")).toBeNull();
    const pfeiffer = [{ name: "Daniela Pfeiffer", party: "FDP", art: "council" },
                      { name: "Anna Pfeiffer", party: null, art: "advisory" }];
    expect(perPartei(pfeiffer, "FDP/Volt")?.name).toBe("Daniela Pfeiffer");
  });
});
