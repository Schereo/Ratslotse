import { describe, expect, it } from "vitest";
import { activeAnalysisSection, analysisSectionHref, analysisSections, analysisSub } from "./analysis-nav";

// Die Liste speist ZWEI Navigationen — das Untermenü der Seitenleiste am
// Schreibtisch und die Reiterleiste auf Telefon und iPad. Was hier falsch
// ist, ist auf beiden falsch; was nur hier stimmt, stimmt auf beiden.

const ALL = { plans: true, ideas: true, elections: true };
const NONE = { plans: false, ideas: false, elections: false };

describe("welche Ziele es gibt", () => {
  it("ohne Schalter die vier Reiter der Analyse, Trends zuerst", () => {
    expect(analysisSections(NONE).map((z) => z.label)).toEqual(["Trends", "Parteien", "Personen", "Ziele"]);
  });

  it("mit Schaltern kommen die beiden eigenen Seiten dazu — am Ende", () => {
    expect(analysisSections(ALL).map((z) => z.key))
      .toEqual(["trends", "parties", "personen", "ziele", "staedte", "wahlen"]);
  });

  it("„Pläne“ ersetzt „Ziele“ unter DERSELBEN Adresse", () => {
    // Alte Links und die App kennen `sub=ziele`; nur der Name wechselt.
    const ziele = analysisSections(NONE).find((z) => z.key === "ziele");
    const plaene = analysisSections({ ...NONE, plans: true }).find((z) => z.key === "ziele");
    expect(plaene?.label).toBe("Pläne");
    expect(plaene?.href).toBe(ziele?.href);
  });

  it("ein abgeschalteter Bereich hat keine Zeile", () => {
    // Ein Anker auf eine Seite, die ein 404 ist, wäre schlechter als keiner.
    const keys = analysisSections({ plans: true, ideas: false, elections: false }).map((z) => z.key);
    expect(keys).not.toContain("staedte");
    expect(keys).not.toContain("wahlen");
  });
});

describe("wohin sie führen", () => {
  it("Trends ist die Analyse ohne `sub` — dieselbe Adresse wie der Hauptpunkt", () => {
    expect(analysisSectionHref("trends")).toBe("/council?tab=analysis");
  });

  it.each([
    ["parties", "/council?tab=analysis&sub=parties"],
    ["personen", "/council?tab=analysis&sub=personen"],
    ["ziele", "/council?tab=analysis&sub=ziele"],
    ["staedte", "/council/ideen"],
    ["wahlen", "/wahlen"],
  ] as const)("%s → %s", (key, href) => {
    expect(analysisSectionHref(key)).toBe(href);
  });
});

describe("welches Ziel der Standort ist", () => {
  it("auf der Analyse-Seite entscheidet `sub`, und Unbekanntes ist Trends", () => {
    expect(activeAnalysisSection("/council", "analysis", null)).toBe("trends");
    expect(activeAnalysisSection("/council", "analysis", "parties")).toBe("parties");
    expect(activeAnalysisSection("/council", "analysis", "erfunden")).toBe("trends");
    // Der abgeschaffte Reiter: Die Seite leitet um, bis dahin steht Trends da.
    expect(analysisSub("finanzen")).toBe("trends");
  });

  it("die anderen Reiter von /council gehören nicht zur Analyse", () => {
    // Fünf Navigationspunkte zeigen auf /council — `sub` allein reicht nicht.
    expect(activeAnalysisSection("/council", null, null)).toBeNull();
    expect(activeAnalysisSection("/council", "sessions", "parties")).toBeNull();
    expect(activeAnalysisSection("/dashboard", "analysis", null)).toBeNull();
  });

  it.each([
    ["/council/person", "personen"],
    ["/council/neuer-rat", "personen"],
    ["/council/plan", "ziele"],
    ["/council/ideen", "staedte"],
    ["/council/ideen/bewegung", "staedte"],
    ["/wahlen", "wahlen"],
    ["/wahlen/ratswahl-2026", "wahlen"],
    ["/wahlabend", "wahlen"],
  ] as const)("die Detailseite %s gehört zu „%s“", (pathname, section) => {
    // `tab` und `sub` einer Detailseite zählen nicht: Sie tragen eigene
    // Parameter, die zufällig genauso heißen können.
    expect(activeAnalysisSection(pathname, null, null)).toBe(section);
    expect(activeAnalysisSection(pathname, "analysis", "parties")).toBe(section);
  });

  it("ein Pfad, der nur so anfängt, ist keine Detailseite", () => {
    expect(activeAnalysisSection("/council/personal", null, null)).toBeNull();
    expect(activeAnalysisSection("/wahlenx", null, null)).toBeNull();
  });
});
