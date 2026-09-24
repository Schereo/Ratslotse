import { describe, expect, it } from "vitest";

import {
  auswahlText, frageMitZitat, knopfPosition, MARKIERUNG_MIN, markierungAufbereiten,
  markierungInZeile,
  SELECTION_MAX, ZITAT_ANZEIGE_MAX,
} from "./markieren";

describe("markierungAufbereiten", () => {
  it("faltet Leerraum — Tabellenzellen kommen mit Zeilenumbrüchen", () => {
    expect(markierungAufbereiten("  391,5\n Mio. €\t")).toEqual({
      text: "391,5 Mio. €", gekuerzt: false,
    });
  });

  it("nimmt schon zwei Zeichen — „VE“ ist eine Abkürzung, kein Klick", () => {
    expect(MARKIERUNG_MIN).toBe(2);
    expect(markierungAufbereiten("VE")?.text).toBe("VE");
    expect(markierungAufbereiten("V")).toBeNull();
    expect(markierungAufbereiten("   ")).toBeNull();
    expect(markierungAufbereiten(null)).toBeNull();
  });

  it("zählt Zeichen, nicht UTF-16-Einheiten", () => {
    // Ein Emoji ist ein Zeichen, aber zwei Einheiten — „x😀" hat zwei Zeichen.
    expect(markierungAufbereiten("x😀")?.text).toBe("x😀");
  });

  it("lässt eine Markierung genau an der Grenze ungekürzt", () => {
    const genau = "a".repeat(SELECTION_MAX);
    expect(markierungAufbereiten(genau)).toEqual({ text: genau, gekuerzt: false });
  });

  it("kürzt eine lange Markierung so, dass sie samt „ …“ in die Grenze passt", () => {
    // Der Server nimmt höchstens SELECTION_MAX (`ExplainBody.selection`);
    // darüber gäbe es 422 statt einer Antwort.
    const lang = "Wort ".repeat(700);
    const aus = markierungAufbereiten(lang)!;
    expect(aus.gekuerzt).toBe(true);
    expect([...aus.text].length).toBeLessThanOrEqual(SELECTION_MAX);
    expect(aus.text.endsWith(" …")).toBe(true);
  });
});

describe("markierungInZeile", () => {
  it("setzt die Markierung in ihre Zeile — so ist klar, WELCHE 8,0 Mio. gemeint sind", () => {
    // Der Fall aus dem Review zu #1517: zwei Kredite über 8,0 Mio. € im
    // selben Baustein, markiert war der aus dem Mai.
    expect(markierungInZeile(
      "Mai 2026 · Kreditaufnahme · Bäderbetrieb Oldenburg · ", "8,0 Mio. €", " 3,43 %",
    )).toEqual({
      text: "Mai 2026 · Kreditaufnahme · Bäderbetrieb Oldenburg · »8,0 Mio. €« 3,43 %",
      gekuerzt: false,
    });
  });

  it("lässt eine Markierung, die die ganze Zeile ist, unverändert", () => {
    expect(markierungInZeile("", "Mai 2026 · Kreditaufnahme", "")).toEqual({
      text: "Mai 2026 · Kreditaufnahme", gekuerzt: false,
    });
    // Nur Leerraum drumherum zählt nicht als Zeile.
    expect(markierungInZeile("  \n", "Kreditaufnahme", " ")?.text).toBe("Kreditaufnahme");
  });

  it("setzt keine Leerzeichen, die nicht da waren — ein halbes Wort bleibt ein Wort", () => {
    expect(markierungInZeile("Kredit", "aufnahme", "n 2026")?.text).toBe("Kredit»aufnahme«n 2026");
  });

  it("entschärft Marken-Zeichen, die schon auf der Seite stehen", () => {
    expect(markierungInZeile("Das »Bäderbad« ", "kostet", " viel")?.text)
      .toBe("Das \"Bäderbad\" »kostet« viel");
  });

  it("kürzt eine zu lange Zeile um die Markierung herum — die Markierung nie", () => {
    const vor = "links ".repeat(300);
    const nach = " rechts".repeat(300);
    const aus = markierungInZeile(vor, "8,0 Mio. €", nach)!;
    expect([...aus.text].length).toBeLessThanOrEqual(SELECTION_MAX);
    expect(aus.text).toContain("»8,0 Mio. €«");
    expect(aus.text.startsWith("… ")).toBe(true);
    expect(aus.text.endsWith(" …")).toBe(true);
    // Was direkt an der Markierung steht, bleibt: Es ist der Kontext.
    expect(aus.text).toContain("links »8,0 Mio. €« rechts");
    expect(aus.gekuerzt).toBe(false);
  });

  it("gibt einer kurzen Seite nur, was sie braucht — den Rest bekommt die andere", () => {
    const aus = markierungInZeile("Mai 2026 · ", "8,0 Mio. €", " x".repeat(800))!;
    expect(aus.text.startsWith("Mai 2026 · »8,0 Mio. €«")).toBe(true);
    expect([...aus.text].length).toBeLessThanOrEqual(SELECTION_MAX);
    expect([...aus.text].length).toBeGreaterThan(SELECTION_MAX - 5);
  });

  it("schickt eine schon zu lange Markierung allein, gekürzt", () => {
    const aus = markierungInZeile("vor ", "y".repeat(3000), " nach")!;
    expect(aus.gekuerzt).toBe(true);
    expect(aus.text).not.toContain("»");
    expect([...aus.text].length).toBeLessThanOrEqual(SELECTION_MAX);
  });

  it("verwirft ein einzelnes Zeichen auch mit Zeile", () => {
    expect(markierungInZeile("Mai 2026 ", "€", " x")).toBeNull();
  });
});

describe("auswahlText", () => {
  const seite = () => ({
    nodeType: 1, closest: () => null,
  }) as unknown as Element;
  const auswahl = (text: string, el: unknown = seite()): Selection => ({
    isCollapsed: false, rangeCount: 1, anchorNode: el, focusNode: el, toString: () => text,
  } as unknown as Selection);

  it("liefert den aufbereiteten Text einer erlaubten Auswahl", () => {
    expect(auswahlText(auswahl(" Verpflichtungs-\nermächtigung "), null))
      .toBe("Verpflichtungs- ermächtigung");
  });

  it("liefert nichts aus Lottis Fenster", () => {
    const fenster = { contains: () => true } as unknown as Element;
    expect(auswahlText(auswahl("Lottis eigene Antwort"), fenster)).toBe("");
  });

  it("liefert nichts für ein einzelnes Zeichen", () => {
    expect(auswahlText(auswahl("a"), null)).toBe("");
  });

  it("hält die Server-Grenze auch hier ein — dieser Text geht bei jeder getippten Frage mit", () => {
    expect([...auswahlText(auswahl("x".repeat(5000)), null)].length)
      .toBeLessThanOrEqual(SELECTION_MAX);
  });
});

describe("frageMitZitat", () => {
  it("setzt das Zitat vor die Frage — so steht es im Verlauf", () => {
    expect(frageMitZitat({ question: "Was bedeutet das?", zitat: "391,5 Mio. €" }))
      .toBe("„391,5 Mio. €“ — Was bedeutet das?");
  });

  it("lässt eine Frage ohne Zitat unverändert", () => {
    expect(frageMitZitat({ question: "Was sehe ich hier?" })).toBe("Was sehe ich hier?");
    expect(frageMitZitat({ question: "Was sehe ich hier?", zitat: "" })).toBe("Was sehe ich hier?");
  });

  it("kürzt ein langes Zitat für die Anzeige", () => {
    const aus = frageMitZitat({ question: "Was bedeutet das?", zitat: "a ".repeat(200) });
    // Zitat höchstens ZITAT_ANZEIGE_MAX Zeichen + „ …“ + die Anführungszeichen.
    expect(aus.length).toBeLessThan(ZITAT_ANZEIGE_MAX + 30);
    expect(aus).toContain(" …“ — Was bedeutet das?");
  });
});

describe("knopfPosition", () => {
  const fenster = { breite: 1280, hoehe: 800 };
  const knopf = { breite: 120, hoehe: 36 };
  const zeile = (top: number, left: number, right: number) =>
    ({ top, bottom: top + 20, left, right });

  it("steht unter dem Ende der Markierung, mittig", () => {
    const r = zeile(300, 400, 600);
    const lage = knopfPosition({ start: r, ende: r, knopf, fenster, abstand: 10 })!;
    expect(lage.lage).toBe("unter");
    expect(lage.y).toBe(330);
    expect(lage.x).toBe(600 - 60);
  });

  it("überdeckt nie die Markierung selbst", () => {
    const start = zeile(300, 400, 1000);
    const ende = zeile(320, 100, 350);
    const lage = knopfPosition({ start, ende, knopf, fenster, abstand: 10 })!;
    expect(lage.y).toBeGreaterThanOrEqual(ende.bottom);
  });

  it("hält sich im Fenster, auch wenn die Markierung am rechten Rand endet", () => {
    const r = zeile(300, 1200, 1275);
    const lage = knopfPosition({ start: r, ende: r, knopf, fenster, abstand: 10 })!;
    expect(lage.x + knopf.breite).toBeLessThanOrEqual(fenster.breite - 8);
    const links = zeile(300, 0, 10);
    expect(knopfPosition({ start: links, ende: links, knopf, fenster, abstand: 10 })!.x)
      .toBeGreaterThanOrEqual(8);
  });

  it("weicht nach OBEN über den Anfang aus, wenn unten kein Platz ist", () => {
    const r = zeile(760, 400, 600);
    const lage = knopfPosition({ start: r, ende: r, knopf, fenster, abstand: 10 })!;
    expect(lage.lage).toBe("ueber");
    expect(lage.y + knopf.hoehe).toBeLessThanOrEqual(r.top);
  });

  it("rechnet die Tab-Leiste unten ab", () => {
    // Handy: 844 hoch, 64 px Tab-Leiste. Unter der Zeile bei 740 wäre Platz im
    // Fenster, aber nicht über der Leiste.
    const handy = { breite: 390, hoehe: 844 };
    const r = zeile(740, 40, 200);
    const lage = knopfPosition({ start: r, ende: r, knopf, fenster: handy, abstand: 34, unten: 64 })!;
    expect(lage.lage).toBe("ueber");
  });

  it("klebt am Rand, wenn die Markierung den ganzen Bildschirm füllt", () => {
    const start = zeile(-500, 0, 1000);
    const ende = zeile(1200, 0, 300);
    const lage = knopfPosition({ start, ende, knopf, fenster, abstand: 10 })!;
    expect(lage.lage).toBe("rand");
    expect(lage.y + knopf.hoehe).toBeLessThanOrEqual(fenster.hoehe - 8);
  });

  it("verschwindet, wenn die Markierung aus dem Bild gescrollt ist", () => {
    const oben = zeile(-200, 0, 300);
    expect(knopfPosition({ start: oben, ende: oben, knopf, fenster, abstand: 10 })).toBeNull();
    const unten = zeile(900, 0, 300);
    expect(knopfPosition({ start: unten, ende: unten, knopf, fenster, abstand: 10 })).toBeNull();
  });

  it("hält am Touchgerät mehr Abstand — der Anfasser sitzt unter dem Ende", () => {
    const r = zeile(300, 100, 200);
    const maus = knopfPosition({ start: r, ende: r, knopf, fenster, abstand: 10 })!;
    const touch = knopfPosition({ start: r, ende: r, knopf, fenster, abstand: 34 })!;
    expect(touch.y - maus.y).toBe(24);
  });
});
