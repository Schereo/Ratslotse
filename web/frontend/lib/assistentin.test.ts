import { describe, expect, it } from "vitest";

import {
  auswahlText, ernteElement, gedaechtnis, kuerze, ohneNamen, refsAus, routeAus,
  seitenTitel, seitenUeberschrift, trenneWeiter, ueberschriftenPfad, zaesur,
} from "./assistentin";

describe("routeAus", () => {
  it("wirft die Query weg — sie trägt alles Persönliche", () => {
    expect(routeAus("/council/decision", "?id=8525")).toBe("/council/decision");
    expect(routeAus("/fragen", "?q=Was%20kostet%20das%20Stadion")).toBe("/fragen");
  });

  it("behält die vier Register von /council — sie sind Seiten, keine Filter", () => {
    expect(routeAus("/council", "?tab=sessions")).toBe("/council?tab=sessions");
    expect(routeAus("/council", "?tab=themen")).toBe("/council?tab=themen");
  });

  it("verwirft ein erfundenes Register, statt es durchzureichen", () => {
    expect(routeAus("/council", "?tab=geheim")).toBe("/council");
  });

  it("schneidet den Schrägstrich ab, den der statische Export anhängt", () => {
    expect(routeAus("/haushalt/schulden/")).toBe("/haushalt/schulden");
    expect(routeAus("/")).toBe("/");
  });
});

describe("refsAus", () => {
  it("liest die Kennungen der jeweiligen Seite", () => {
    expect(refsAus("?id=8525", "/council/decision")).toEqual({ decision_id: 8525 });
    expect(refsAus("?ksinr=4711")).toEqual({ ksinr: 4711 });
    expect(refsAus("?ort=neu-donnerschwee", "/karte")).toEqual({ place_id: "neu-donnerschwee" });
    expect(refsAus("?year=2025")).toEqual({ year: 2025 });
  });

  it("übersetzt die beiden Steckbrief-Parameter auf denselben Namen", () => {
    expect(refsAus("?name=Soziales")).toEqual({ area: "Soziales" });
    expect(refsAus("?art=gewerbesteuer")).toEqual({ area: "gewerbesteuer" });
  });

  it("nimmt NICHTS mit, was nicht in der Liste steht", () => {
    // Genau hier stünde sonst die Suchanfrage.
    expect(refsAus("?q=Stadion&tab=decisions&von=mail")).toEqual({});
  });

  it("liest `?id=` auf der Ort-Seite als Kürzel, nicht als Nummer", () => {
    // Der Fehler der ersten Fassung: `Number("neu-donnerschwee")` ist NaN,
    // die Kennung fiel still heraus, und Lotti wusste auf der Ort-Seite
    // nicht, um welchen Ort es geht. Gefunden hat das der Wächter gegen
    // umbenannte Werte (scripts/pruefe_alte_werte.py), kein Test hier.
    expect(refsAus("?id=neu-donnerschwee", "/council/ort"))
      .toEqual({ place_id: "neu-donnerschwee" });
    expect(refsAus("?id=8525", "/council/ort")).toEqual({ place_id: "8525" });
  });

  it("verwirft unsinnige Zahlen, statt sie ans Backend zu schicken", () => {
    expect(refsAus("?id=abc", "/council/decision")).toEqual({});
    expect(refsAus("?id=-3", "/council/decision")).toEqual({});
    expect(refsAus("?year=1200")).toEqual({});
  });
});

describe("kuerze", () => {
  it("faltet Leerraum", () => {
    expect(kuerze("a   \n\t b ", 50)).toBe("a b");
  });

  it("schneidet hart und sagt es", () => {
    const aus = kuerze("x".repeat(300), 100);
    expect(aus.length).toBeLessThanOrEqual(102);
    expect(aus.endsWith("…")).toBe(true);
  });

  it("zerlegt kein Zeichen in der Mitte", () => {
    // `slice(0, n)` auf einem String mit Emoji trennt sonst ein Surrogatpaar,
    // und im Prompt steht ein Ersatzzeichen.
    const aus = kuerze("🏟️🏟️🏟️🏟️", 2);
    expect(aus).not.toContain("�");
  });
});

describe("trenneWeiter", () => {
  it("trennt die Marke ab", () => {
    expect(trenneWeiter("Ein Satz.\nWEITER: ratsfrage"))
      .toEqual({ text: "Ein Satz.", next: "ratsfrage" });
  });

  it("lässt Text ohne Marke unberührt", () => {
    expect(trenneWeiter("Nur Text.")).toEqual({ text: "Nur Text.", next: null });
  });

  it("verwirft ein erfundenes Ziel — die Zeile verschwindet trotzdem", () => {
    expect(trenneWeiter("Ein Satz.\nWEITER: systemzugriff"))
      .toEqual({ text: "Ein Satz.", next: null });
  });
});

// --- DOM-nahe Funktionen ----------------------------------------------------
// Sie brauchen ein Dokument; vitest läuft hier ohne jsdom, deshalb der
// kleinstmögliche Nachbau. Die Alternative wäre eine ganze DOM-Nachbildung
// für drei Funktionen — das kostet Sekunden je Lauf (s. web/frontend/CLAUDE.md).

function fakeElement(opts: {
  attrs?: Record<string, string>; text?: string; kopf?: string; innen?: Element | null;
}): HTMLElement {
  const attrs = opts.attrs ?? {};
  return {
    getAttribute: (n: string) => attrs[n] ?? null,
    querySelector: () => (opts.kopf ? { textContent: opts.kopf } : null),
    closest: () => opts.innen ?? null,
    innerText: opts.text ?? "",
    textContent: opts.text ?? "",
  } as unknown as HTMLElement;
}

describe("ernteElement", () => {
  it("nimmt Schlüssel, Titel und Text — und kürzt den Text", () => {
    const el = fakeElement({
      attrs: { "data-erklaer": "schulden.rate-treppe", "data-erklaer-titel": "Rate-Treppe" },
      text: "Tilgung je Jahr.   2024: 31,2 Mio. €",
    });
    expect(ernteElement(el)).toEqual({
      key: "schulden.rate-treppe",
      title: "Rate-Treppe",
      text: "Tilgung je Jahr. 2024: 31,2 Mio. €",
    });
  });

  it("nimmt die Überschrift im Element, wenn kein Titel gesetzt ist", () => {
    const el = fakeElement({ attrs: { "data-erklaer": "hh.tafel" }, kopf: "Die Tafel", text: "x" });
    expect(ernteElement(el).title).toBe("Die Tafel");
  });

  it("deckelt den Text bei 1200 Zeichen", () => {
    const el = fakeElement({ attrs: { "data-erklaer": "x" }, text: "y".repeat(5000) });
    expect(ernteElement(el).text.length).toBeLessThanOrEqual(1202);
  });
});

describe("auswahlText", () => {
  const auswahl = (text: string, el: unknown): Selection => ({
    isCollapsed: false, rangeCount: 1, anchorNode: el, toString: () => text,
  } as unknown as Selection);

  it("nimmt eine Markierung auf der Seite", () => {
    const el = fakeElement({});
    Object.defineProperty(el, "nodeType", { value: 1 });
    expect(auswahlText(auswahl("Verpflichtungsermächtigung", el), null))
      .toBe("Verpflichtungsermächtigung");
  });

  it("nimmt NICHTS aus einem Eingabefeld — das ist getippter Text der Person", () => {
    const el = fakeElement({ innen: {} as Element });
    Object.defineProperty(el, "nodeType", { value: 1 });
    expect(auswahlText(auswahl("mein Passwort", el), null)).toBe("");
  });

  it("nimmt NICHTS aus dem Lotti-Fenster selbst", () => {
    const el = fakeElement({});
    Object.defineProperty(el, "nodeType", { value: 1 });
    const fenster = { contains: () => true } as unknown as Element;
    expect(auswahlText(auswahl("Lottis eigene Antwort", el), fenster)).toBe("");
  });

  it("ignoriert eine Markierung unter drei Zeichen — das ist ein Klick", () => {
    const el = fakeElement({});
    Object.defineProperty(el, "nodeType", { value: 1 });
    expect(auswahlText(auswahl("ab", el), null)).toBe("");
  });

  it("kommt mit einer leeren Auswahl zurecht", () => {
    expect(auswahlText(null, null)).toBe("");
  });
});

describe("ueberschriftenPfad", () => {
  const dok = (h1: string, koepfe: { text: string; vorElement: boolean }[]): Document => ({
    querySelector: () => (h1 ? { textContent: h1 } : null),
    querySelectorAll: () => koepfe.map((k) => ({
      textContent: k.text,
      // DOCUMENT_POSITION_FOLLOWING = 4: das Element folgt dem Kopf.
      compareDocumentPosition: () => (k.vorElement ? 4 : 2),
    })),
  } as unknown as Document);

  it("verbindet die Seitenüberschrift mit der nächsten darüber", () => {
    const el = {} as Element;
    expect(ueberschriftenPfad(el, dok("Schulden", [
      { text: "Der Stand", vorElement: true },
      { text: "Die Tilgung", vorElement: true },
      { text: "Weiter unten", vorElement: false },
    ]))).toBe("Schulden › Die Tilgung");
  });

  it("nimmt ohne Element nur die Seitenüberschrift", () => {
    expect(ueberschriftenPfad(null, dok("Schulden", []))).toBe("Schulden");
  });
});

describe("ohneNamen", () => {
  it("streicht den Anzeigenamen aus dem Gruß", () => {
    expect(ohneNamen("Moin, Ratsfrau!", "Ratsfrau")).toBe("Moin!");
  });

  it("streicht auch den Vornamen allein", () => {
    expect(ohneNamen("Moin, Anna!", "Anna Musterfrau")).toBe("Moin!");
  });

  it("lässt einen kurzen Namen stehen", () => {
    // Ein Konto namens „Al" hätte aus „Alexanderfeld" ein „exanderfeld"
    // gemacht — der Riegel zerstörte die Seite, statt sie zu schützen.
    expect(ohneNamen("Beschluss zu Alexanderfeld", "Al"))
      .toBe("Beschluss zu Alexanderfeld");
  });

  it("streicht nur ganze Wörter", () => {
    expect(ohneNamen("Inanspruchnahme im Januar", "Ina"))
      .toBe("Inanspruchnahme im Januar");
    expect(ohneNamen("Ina fragt", "Ina")).toBe("fragt");
  });

  it("kommt ohne Namen zurecht", () => {
    expect(ohneNamen("Schulden", null)).toBe("Schulden");
  });
});

describe("seitenUeberschrift und seitenTitel", () => {
  const dok = (h1: string, titel = "Heute"): Document => ({
    title: titel,
    querySelector: () => (h1 ? { textContent: h1 } : null),
  } as unknown as Document);

  it("lässt einen reinen Gruß ganz weg", () => {
    // Auf `/dashboard` ist die `h1` „Moin, Ratsfrau!" — bleibt nach dem
    // Streichen nur „Moin!", sagt das nichts über die Seite.
    expect(seitenUeberschrift(dok("Moin, Ratsfrau!"), "Ratsfrau")).toBe("");
  });

  it("behält eine echte Überschrift", () => {
    expect(seitenUeberschrift(dok("Schulden"), "Ratsfrau")).toBe("Schulden");
  });

  it("nimmt den Anwendungsnamen aus dem Fenstertitel", () => {
    expect(seitenTitel(dok("", "Heute — Ratslotse"))).toBe("Heute");
  });
});

describe("ueberschriftenPfad mit Anzeigenamen", () => {
  const dok = (h1: string): Document => ({
    title: "Heute",
    querySelector: () => ({ textContent: h1 }),
    querySelectorAll: () => [],
  } as unknown as Document);

  it("schickt auf der Startseite gar keine Überschrift", () => {
    expect(ueberschriftenPfad(null, dok("Moin, Ratsfrau!"), "Ratsfrau")).toBe("");
  });
});

describe("gedaechtnis", () => {
  const runde = (route: string | undefined, answer = "A") => ({ route, answer });

  it("nimmt nur Runden derselben Seite", () => {
    // Der Befund vom 21.09.2026: Auf der Schulden-Seite standen drei Runden
    // von der Personen-Seite als Vorgeschichte im Prompt.
    const turns = [
      runde("/council/person", "Margrit Conty …"),
      runde("/haushalt/schulden", "Die Rate-Treppe …"),
    ];
    expect(gedaechtnis(turns, "/haushalt/schulden"))
      .toEqual([runde("/haushalt/schulden", "Die Rate-Treppe …")]);
  });

  it("zählt eine Runde ohne Route als fremd", () => {
    // So sehen Runden aus einem älteren Tab-Speicher aus — kein
    // Migrationscode, sie fallen einfach aus dem Gedächtnis.
    expect(gedaechtnis([runde(undefined)], "/dashboard")).toEqual([]);
  });

  it("lässt leere und fehlgeschlagene Runden draußen", () => {
    const turns = [
      { route: "/dashboard", answer: "" },
      { route: "/dashboard", answer: "Das hat nicht geklappt.", fehler: true },
      { route: "/dashboard", answer: "Hier steht …" },
    ];
    expect(gedaechtnis(turns, "/dashboard")).toEqual([{ route: "/dashboard", answer: "Hier steht …" }]);
  });

  it("nimmt höchstens die letzten drei — und zwar die letzten", () => {
    const turns = [1, 2, 3, 4].map((n) => runde("/dashboard", `A${n}`));
    expect(gedaechtnis(turns, "/dashboard", 3).map((t) => t.answer))
      .toEqual(["A2", "A3", "A4"]);
  });

  it("unterscheidet die vier Register von /council", () => {
    const turns = [runde("/council?tab=sessions"), runde("/council?tab=themen")];
    expect(gedaechtnis(turns, "/council?tab=themen")).toHaveLength(1);
  });
});

describe("zaesur", () => {
  const t = (route: string, seite?: string) => ({ route, seite, answer: "A" });

  it("steht vor der ersten Runde einer neuen Seite", () => {
    const turns = [t("/dashboard", "Heute"), t("/haushalt/schulden", "Schulden")];
    expect(zaesur(turns, 1)).toBe("Schulden");
  });

  it("steht nicht über der ersten Runde überhaupt", () => {
    expect(zaesur([t("/dashboard", "Heute")], 0)).toBeNull();
  });

  it("wiederholt sich nicht innerhalb derselben Seite", () => {
    const turns = [t("/dashboard", "Heute"), t("/dashboard", "Heute")];
    expect(zaesur(turns, 1)).toBeNull();
  });

  it("nimmt die Route, wenn der Seitenname fehlt", () => {
    // Ein aus der Liste geladenes Gespräch trägt die Route im Schnappschuss,
    // aber keinen Seitennamen.
    const turns = [t("/dashboard", "Heute"), t("/council/decision")];
    expect(zaesur(turns, 1)).toBe("/council/decision");
  });
});
