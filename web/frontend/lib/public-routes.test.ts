import { afterEach, describe, expect, it, vi } from "vitest";
import {
  OEFFENTLICHE_PFADE, istOeffentlich, mitRuecksprung, sicheresZiel, zielNachAnmeldung,
} from "./public-routes";

// Zwei Grenzen in einer Datei. Die erste sagt, welche Seite ohne Konto etwas
// zeigt; die zweite entscheidet, wohin nach der Anmeldung gesprungen wird —
// und das Ziel kommt aus der ADRESSZEILE, ist also fremde Eingabe.

describe("istOeffentlich", () => {
  it.each([...OEFFENTLICHE_PFADE])("%s ist offen", (p) => {
    expect(istOeffentlich(p)).toBe(true);
  });

  it("erkennt auch die Schreibweise mit Schluss-Schrägstrich", () => {
    // Der statische Export legt die Seiten als Verzeichnis ab, der Browser
    // hängt dann einen Schrägstrich an. Beide müssen treffen — sonst stünde
    // in der App vor einem geteilten Link doch wieder die Anmeldewand.
    for (const p of OEFFENTLICHE_PFADE) expect(istOeffentlich(`${p}/`)).toBe(true);
  });

  it("hält alles Persönliche zu", () => {
    for (const p of ["/dashboard", "/topics", "/bookmarks", "/account", "/abos", "/council"]) {
      expect(istOeffentlich(p)).toBe(false);
    }
  });

  it("ist kein Präfix-Vergleich", () => {
    // `/council/decisionXYZ` ist keine öffentliche Seite. Ein `startsWith`
    // hätte sie durchgelassen.
    expect(istOeffentlich("/council/decisionXYZ")).toBe(false);
    expect(istOeffentlich("/council/decision/geheim")).toBe(false);
  });

  it("sagt bei leer und null nein", () => {
    for (const p of ["", null, undefined]) expect(istOeffentlich(p)).toBe(false);
  });
});

describe("sicheresZiel — das Ziel kommt aus der Adresszeile", () => {
  it("lässt einen eigenen Pfad durch", () => {
    expect(sicheresZiel("/council/decision?id=1")).toBe("/council/decision?id=1");
    expect(sicheresZiel("/")).toBe("/");
  });

  it("verwirft eine Weiterleitung nach außen", () => {
    // `//fremde.example` ist für den Browser ein absoluter Verweis auf einen
    // fremden Host — der klassische Weg, eine Anmeldung umzuleiten.
    for (const roh of ["//example.org/", "//example.org", "/\\example.org", "https://example.org",
                       "http://example.org", "javascript:alert(1)", "example.org"]) {
      expect(sicheresZiel(roh), roh).toBeNull();
    }
  });

  it("repariert nichts, sondern verwirft", () => {
    // Aus `//example.org` ein `/example.org` zu machen wäre der naheliegende
    // und falsche Weg: Man rät dann, was jemand gemeint hat.
    expect(sicheresZiel("//example.org")).toBeNull();
  });

  it("verwirft leer und null", () => {
    for (const roh of ["", null, undefined]) expect(sicheresZiel(roh)).toBeNull();
  });
});

describe("mitRuecksprung", () => {
  it("kodiert das Ziel", () => {
    expect(mitRuecksprung("/login", "/council/decision?id=1"))
      .toBe("/login?weiter=%2Fcouncil%2Fdecision%3Fid%3D1");
  });

  it("verliert die Query des Ziels nicht", () => {
    // Genau das ging vorher schief: `?weiter=/x?id=1` unkodiert zerfällt in
    // zwei Parameter, und die Kennung war weg.
    const url = new URL(`http://x${mitRuecksprung("/login", "/council/decision?id=42")}`);
    expect(url.searchParams.get("weiter")).toBe("/council/decision?id=42");
  });
});

describe("zielNachAnmeldung", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("nimmt ein sicheres `weiter`", () => {
    vi.stubGlobal("window", { location: { search: "?weiter=%2Ftopics" } });
    expect(zielNachAnmeldung()).toBe("/topics");
  });

  it("fällt auf das Dashboard zurück — bei fehlendem UND bei fremdem Ziel", () => {
    for (const search of ["", "?weiter=", "?weiter=%2F%2Fexample.org", "?weiter=https%3A%2F%2Fexample.org"]) {
      vi.stubGlobal("window", { location: { search } });
      expect(zielNachAnmeldung(), search).toBe("/dashboard");
    }
  });

  it("liefert auf dem Server das Dashboard, statt auf `window` zuzugreifen", () => {
    vi.stubGlobal("window", undefined);
    expect(zielNachAnmeldung()).toBe("/dashboard");
  });
});
