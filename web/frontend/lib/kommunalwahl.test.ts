import { describe, expect, it } from "vitest";
import {
  WAHLTAG, belegHref, datenlageBalken, kennzahlen, listenKacheln, marke,
  nahFern, ohneProgramm, stand, streitEinigkeit, themaKeys, themenKacheln,
  vergleichsSlugs,
} from "./kommunalwahl";

// Der Wahlprogramm-Vergleich rechnet aus `kommunalwahl/data.json`. Anders als
// der Rest von `lib/` liest er ECHTE Daten aus dem Repo — das ist hier
// richtig: Der Vergleich behauptet Aussagen über neun Listen, und die
// gefährlichen Fehler sind nicht Ausnahmen, sondern falsche Zuordnungen.
//
// Geprüft wird deshalb die FORM und die innere Stimmigkeit, nicht der Inhalt:
// Wer die Programme neu einliest, soll nicht wegen einer geänderten Zahl einen
// roten Test bekommen.

describe("Grunddaten", () => {
  it("kennt den Wahltag", () => {
    expect(WAHLTAG).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(new Date(WAHLTAG).getTime()).not.toBeNaN();
  });

  it("nennt einen Erhebungsstand", () => {
    expect(stand()).toMatch(/^\d{4}-\d{2}-\d{2}/);
  });

  it("vergleicht mehrere Listen, jede genau einmal", () => {
    const s = vergleichsSlugs();
    expect(s.length).toBeGreaterThan(1);
    expect(new Set(s).size).toBe(s.length);
  });
});

describe("marke — Farbe und Kurzname je Liste", () => {
  it("liefert für jede verglichene Liste eine vollständige Marke", () => {
    for (const slug of vergleichsSlugs()) {
      const m = marke(slug);
      expect(m.slug, slug).toBe(slug);
      expect(m.kurz, slug).toBeTruthy();
      expect(m.farbe, slug).toMatch(/^#|^hsl|^rgb|^\d/);
      expect(m.farbeDunkel, slug).toBeTruthy();
      expect(typeof m.landesprogramm, slug).toBe("boolean");
    }
  });

  it("gibt keiner Liste den Kurznamen einer anderen", () => {
    const kurz = vergleichsSlugs().map((s) => marke(s).kurz);
    expect(new Set(kurz).size).toBe(kurz.length);
  });

  it("unterscheidet die Listen farblich", () => {
    const farben = vergleichsSlugs().map((s) => marke(s).farbe.toLowerCase());
    expect(new Set(farben).size).toBe(farben.length);
  });
});

describe("belegHref — jede Aussage führt zu ihrer Fundstelle", () => {
  it("liefert für jede Liste entweder eine Adresse oder ehrlich nichts", () => {
    for (const slug of vergleichsSlugs()) {
      const href = belegHref(slug, 1);
      if (href !== null) expect(href, slug).toMatch(/^https?:\/\//);
    }
  });

  it("hängt die Seite nur an, wo der Sprung auch funktioniert", () => {
    // `#page=N` springt in PDF-Viewern; bei einer Website wäre es sinnlos.
    for (const slug of vergleichsSlugs()) {
      const mit = belegHref(slug, 7);
      const ohne = belegHref(slug, null);
      if (mit && mit.includes("#page=")) {
        expect(mit).toBe(`${ohne}#page=7`);
      }
    }
  });

  it("hängt ohne Seitenzahl nie einen Anker an", () => {
    for (const slug of vergleichsSlugs()) {
      expect(belegHref(slug, null) ?? "").not.toContain("#page=");
    }
  });
});

describe("Die gerechneten Auswertungen", () => {
  it("kennzahlen liefert beschriftete Zahlen", () => {
    const k = kennzahlen();
    expect(k.length).toBeGreaterThan(0);
    for (const z of k) {
      expect(z).toHaveProperty("wert");
      expect(String(z.wert).length).toBeGreaterThan(0);
    }
  });

  it("datenlageBalken zeigt ALLE Listen — auch die ohne Programm", () => {
    // Das ist der Sinn der Datenlage-Grafik: Sie sagt, von wem überhaupt
    // etwas vorliegt. Zeigte sie nur die verglichenen, verschwiege sie genau
    // die Lücke, um die es geht.
    const alle = datenlageBalken().map((b) => b.slug);
    expect(new Set(alle).size).toBe(alle.length);
    for (const s of vergleichsSlugs()) expect(alle, s).toContain(s);
    expect(alle.length).toBeGreaterThanOrEqual(vergleichsSlugs().length);
    for (const b of datenlageBalken()) expect(b.art, b.slug).toBeTruthy();
  });

  it("streitEinigkeit trennt die beiden Seiten überschneidungsfrei", () => {
    // Eine These, die in beiden Listen steht, wäre ein Widerspruch in sich.
    const { streit, einig } = streitEinigkeit();
    const ids = (zeilen: { tid?: string; id?: string }[]) =>
      new Set(zeilen.map((z) => z.tid ?? z.id));
    const beide = [...ids(streit)].filter((x) => ids(einig).has(x));
    expect(beide).toEqual([]);
  });

  it("themenKacheln und themaKeys nennen dieselben Themen", () => {
    const ausKacheln = new Set(themenKacheln().map((t) => t.key));
    for (const key of themaKeys()) expect(ausKacheln.has(key), key).toBe(true);
  });

  it("listenKacheln führt jede Liste genau einmal", () => {
    const slugs = listenKacheln().map((l) => l.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("nahFern paart nie eine Liste mit sich selbst", () => {
    // Jede Zeile ist ein PAAR (a, b) mit einem Abstand. „SPD steht der SPD
    // am nächsten" wäre keine Aussage, sondern ein Rechenfehler.
    for (const n of nahFern()) {
      expect(n.a.slug).not.toBe(n.b.slug);
      expect(["nah", "fern"]).toContain(n.art);
      expect(n.n).toBeGreaterThan(0);
    }
  });

  it("nahFern vergleicht nur Listen, die auch verglichen werden", () => {
    const erlaubt = new Set(vergleichsSlugs());
    for (const n of nahFern()) {
      expect(erlaubt.has(n.a.slug), n.a.slug).toBe(true);
      expect(erlaubt.has(n.b.slug), n.b.slug).toBe(true);
    }
  });

  it("ohneProgramm und vergleichsSlugs überschneiden sich nicht", () => {
    // Wer kein Programm hat, kann nicht verglichen werden — stünde eine Liste
    // in beiden, behauptete die Seite zweierlei über dieselbe.
    const ohne = new Set(ohneProgramm().map((o) => o.slug));
    for (const s of vergleichsSlugs()) expect(ohne.has(s), s).toBe(false);
  });
});
