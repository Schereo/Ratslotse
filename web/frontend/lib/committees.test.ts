import { describe, expect, it } from "vitest";
import {
  committeeExplains, committeeIcon, committeeRank, hasShortCommittee, shortCommittee,
} from "./committees";

// Die amtlichen Oldenburger Gremiennamen sprengen jede Karte, jedes Chip und
// jedes Dropdown. `shortCommittee` ist die eine Stelle, die sie kürzt — und
// zwar sinntragend, nie nach n Zeichen abgeschnitten.

describe("shortCommittee — gepflegte Tabelle", () => {
  it.each([
    ["Rat der Stadt Oldenburg", "Rat"],
    ["Rat der Stadt Oldenburg (Oldb)", "Rat"],
    ["Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit", "Wirtschaft & Digitales"],
    ["Ausschuss für Stadtgrün, Umwelt und Klima", "Stadtgrün & Klima"],
    ["Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau", "Betrieb Gebäudewirtschaft"],
    ["Jugendhilfeausschuss", "Jugendhilfe"],
  ])("%s → %s", (lang, kurz) => {
    expect(shortCommittee(lang)).toBe(kurz);
  });

  it("kennt die historischen Namen aus dem Bestand seit 2018", () => {
    // Ohne sie stünde in alten Sitzungen ein anderer Kurzname als in neuen —
    // und dieselbe Sache sähe nach zwei Gremien aus.
    expect(shortCommittee("Ausschuss für Umwelt und Klimaschutz")).toBe("Umwelt & Klima");
    expect(shortCommittee("Ausschuss für Wirtschaftsförderung und Digitalisierung"))
      .toBe("Wirtschaft & Digitales");
  });

  it("putzt Leerraum, bevor es nachschlägt", () => {
    expect(shortCommittee("  Jugendhilfeausschuss  ")).toBe("Jugendhilfe");
  });
});

describe("shortCommittee — Heuristik für Unbekanntes", () => {
  it("streicht das Präfix „Ausschuss für“", () => {
    expect(shortCommittee("Ausschuss für Neues und Unbekanntes")).toBe("Neues & Unbekanntes");
    expect(shortCommittee("Ausschuss für die Zukunft")).toBe("Zukunft");
  });

  it("macht aus „Xausschuss“ den Kern", () => {
    expect(shortCommittee("Wahlausschuss")).toBe("Wahl");
    expect(shortCommittee("Rechnungsprüfungsausschuss")).toBe("Rechnungsprüfung");
  });

  it("kürzt niemals hart auf n Zeichen", () => {
    // Die Zusage ist NICHT „unverändert" — „und" wird auch hier zu „&". Die
    // Zusage ist, dass nichts mitten im Wort abreißt und der Name lesbar
    // bleibt, statt nach 20 Zeichen mit „…" zu enden.
    const lang = "Gremium mit einem sehr langen und völlig unbekannten Namen";
    const kurz = shortCommittee(lang);
    expect(kurz).toBe("Gremium mit einem sehr langen & völlig unbekannten Namen");
    expect(kurz).not.toContain("…");
    expect(kurz.endsWith("Namen")).toBe(true);
  });

  it("gibt den Originalnamen zurück, wenn nichts Brauchbares übrig bleibt", () => {
    expect(shortCommittee("Ausschuss für")).toBe("Ausschuss für");
  });

  it("liefert für leer und null einen leeren String, nie „undefined“", () => {
    for (const n of ["", null, undefined]) expect(shortCommittee(n)).toBe("");
  });
});

describe("hasShortCommittee — lohnt die Unterzeile?", () => {
  it("nein, wenn der Kurzname der volle ist", () => {
    expect(hasShortCommittee("Verwaltungsausschuss")).toBe(false);
    expect(hasShortCommittee("Rat")).toBe(false);
  });

  it("ja, wenn wirklich gekürzt wurde", () => {
    expect(hasShortCommittee("Rat der Stadt Oldenburg")).toBe(true);
    expect(hasShortCommittee("Jugendhilfeausschuss")).toBe(true);
  });

  it("nein für leer", () => {
    expect(hasShortCommittee("")).toBe(false);
    expect(hasShortCommittee(null)).toBe(false);
  });
});

describe("committeeExplains", () => {
  it("erklärt über den KURZnamen — der volle Name führt zum selben Satz", () => {
    expect(committeeExplains("Rat der Stadt Oldenburg"))
      .toBe(committeeExplains("Rat"));
    expect(committeeExplains("Jugendhilfeausschuss")).toContain("Kitas");
  });

  it("erfindet nichts für Unbekanntes", () => {
    // Die Oberfläche zeigt dann nur den Namen. Ein erfundener Satz wäre
    // schlimmer als keiner.
    expect(committeeExplains("Ausschuss für Neues")).toBe("");
    expect(committeeExplains(null)).toBe("");
  });

  it("jeder erklärte Satz endet als ganzer Satz", () => {
    for (const g of ["Rat", "Verkehr", "Schule", "Sport", "Kultur"]) {
      expect(committeeExplains(g)).toMatch(/\.$/);
    }
  });
});

describe("committeeRank — was die meisten betrifft, steht oben", () => {
  it("der Rat steht ganz vorn", () => {
    expect(committeeRank("Rat der Stadt Oldenburg")).toBe(0);
  });

  it("Fachausschüsse mit Alltagsbezug vor Betriebsausschüssen", () => {
    expect(committeeRank("Ausschuss für Stadtplanung und Bauen"))
      .toBeLessThan(committeeRank("Betriebsausschuss Abfallwirtschaftsbetrieb"));
    expect(committeeRank("Verkehrsausschuss"))
      .toBeLessThan(committeeRank("Verwaltungsausschuss"));
  });

  it("die beiden Namen desselben Umweltausschusses ranken gleich", () => {
    expect(committeeRank("Ausschuss für Umwelt und Klimaschutz"))
      .toBe(committeeRank("Ausschuss für Stadtgrün, Umwelt und Klima"));
  });

  it("Unbekanntes landet hinten, aber nicht im Nichts", () => {
    expect(committeeRank("Ausschuss für Neues")).toBe(50);
    expect(committeeRank(null)).toBe(50);
  });

  it("sortiert eine Liste stabil und nachvollziehbar", () => {
    const liste = ["Sportausschuss", "Rat", "Verkehrsausschuss"];
    expect([...liste].sort((a, b) => committeeRank(a) - committeeRank(b)))
      .toEqual(["Rat", "Verkehrsausschuss", "Sportausschuss"]);
  });
});

describe("committeeIcon", () => {
  it("gibt für jedes bekannte Gremium ein Zeichen", () => {
    for (const g of ["Rat", "Verkehrsausschuss", "Kulturausschuss", "Schulausschuss"]) {
      expect(committeeIcon(g)).toBeTruthy();
    }
  });

  it("fällt auf die Gruppe zurück statt auf nichts", () => {
    // Ein Gremium sind Menschen, die zusammensitzen — nie falsch, nur allgemein.
    const unbekannt = committeeIcon("Ausschuss für Neues");
    expect(unbekannt).toBeTruthy();
    expect(unbekannt).toBe(committeeIcon(null));
  });

  it("unterscheidet die Sachbereiche wirklich", () => {
    expect(committeeIcon("Verkehrsausschuss")).not.toBe(committeeIcon("Kulturausschuss"));
  });
});
