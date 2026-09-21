import { describe, expect, it } from "vitest";

import {
  ankerListe, ankerTreffer, anschlussfragen, auswahlText, chipTitel, daumenZeigen, ernteElement,
  gedaechtnis, kuerze, ohneNamen, ortsfrage, refsAus, routeAus, seitenTitel,
  seitenUeberschrift, trenneWeiter, ueberschriftenPfad, zaesur,
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

describe("daumenZeigen", () => {
  it("steht unter einer Erklärung des Modells", () => {
    expect(daumenZeigen({ answer: "Die Stadt baut …", mode: "explain" })).toBe(true);
  });

  it("steht NICHT unter geprüftem Text ohne Modell", () => {
    // Glossar, Seiten-Wissen, „Lotti erklärt's einfach": Ein Daumen darunter
    // bewertete das Glossar, nicht die Assistentin.
    expect(daumenZeigen({ answer: "Ein Haushaltsplan ist …", mode: "deterministic" })).toBe(false);
  });

  it("steht auch unter einer Ratsantwort aus dem Fenster", () => {
    // Der zweite Antwortweg nimmt denselben Weg wie „Frag den Rat" und ist
    // dort seit jeher bewertbar; `mode` bleibt dabei leer.
    expect(daumenZeigen({ answer: "Der Rat hat …", mode: null, ratsfrage: true })).toBe(true);
  });

  it("steht erst, wenn der Strom durch ist", () => {
    // Während des Stroms steht die Antwort schon da, `mode` kommt erst mit
    // dem `done`-Rahmen — bewerten kann man nur, was fertig ist.
    expect(daumenZeigen({ answer: "Die Sta", mode: null })).toBe(false);
    expect(daumenZeigen({ answer: "", mode: "explain" })).toBe(false);
  });

  it("steht nicht unter einer Fehlermeldung", () => {
    expect(daumenZeigen({ answer: "Erklärung fehlgeschlagen.", mode: "explain", fehler: true })).toBe(false);
  });
});

/* ── „Zeig mir": die Lotsin ─────────────────────────────────────────────── */

describe("ortsfrage", () => {
  it.each([
    "Wo finde ich die Rate-Treppe?",
    "wo steht, was die Stadt an Zinsen zahlt",
    "Wo sehe ich die Schulden je Einwohner?",
    "Wo ist der Kassenzettel?",
    "Gibt es hier eine Tabelle mit den Teilhaushalten?",
    "Zeig mir die Anzeigetafel",
    "zeige mir bitte die Kredite",
    "Finde ich hier die Zinsen?",
  ])("erkennt %j als Frage nach dem Ort", (frage) => {
    expect(ortsfrage(frage)).toBe(true);
  });

  it.each([
    "Was ist eine Rate-Treppe?",
    "Wie hoch sind die Schulden?",
    // Die Abgrenzung, auf die es ankommt: Das ist eine ARCHIV-Frage. Sie
    // gehört ans Modell samt Weiterreichung, nicht an einen Chip.
    "Wo wurde das beschlossen?",
    "Warum steigen die Zinsen?",
    "",
  ])("lässt %j ans Modell", (frage) => {
    expect(ortsfrage(frage)).toBe(false);
  });
});

const ANKER = [
  { key: "haushalt-schulden.tafel", titel: "Die Anzeigetafel" },
  { key: "haushalt-schulden.kredite", titel: "Kredite und Zinsen" },
  { key: "haushalt-schulden.rate-treppe", titel: "Rate-Treppe" },
  { key: "haushalt-schulden.buergschaften", titel: "Bürgschaften" },
];

describe("ankerTreffer", () => {
  it("findet den Baustein am gemeinsamen Inhaltswort", () => {
    expect(ankerTreffer("Wo steht, was die Stadt an Zinsen zahlt?", ANKER))
      .toEqual([ANKER[1]]);
  });

  it("lässt sich von „Stadt“ nicht ablenken", () => {
    // Gemessen im Browser (22.09.2026): Die Bühne heißt „Drei Zählweisen,
    // eine Stadt · Stand 31.12.2024" — über „Stadt" traf sie dieselbe Frage
    // und stand als erster Chip vor dem richtigen Baustein.
    const mitBuehne = [{ key: "hh.buehne", titel: "Drei Zählweisen, eine Stadt" }, ...ANKER];
    expect(ankerTreffer("Wo steht, was die Stadt an Zinsen zahlt?", mitBuehne))
      .toEqual([ANKER[1]]);
  });

  it("findet auch über Umlaute — die Faltung ist dieselbe wie im Backend", () => {
    expect(ankerTreffer("Wo finde ich die Bürgschaften?", ANKER)).toEqual([ANKER[3]]);
    // Und ohne Umlaut getippt: „buergschaften" fällt auf denselben Stamm.
    expect(ankerTreffer("wo sind die Buergschaften", ANKER)).toEqual([ANKER[3]]);
  });

  it("reiht die beste Übereinstimmung nach vorn", () => {
    const treffer = ankerTreffer("Wo finde ich die Rate-Treppe?", ANKER);
    expect(treffer[0]).toEqual(ANKER[2]);
  });

  it("gibt höchstens drei zurück", () => {
    const viele = Array.from({ length: 8 }, (_, i) => (
      { key: `k${i}`, titel: `Zinsen Teil ${i}` }));
    expect(ankerTreffer("Wo stehen die Zinsen?", viele)).toHaveLength(3);
  });

  it("trifft lieber nichts als das Falsche", () => {
    // Kein gemeinsames Inhaltswort — dann geht die Frage ans Modell, statt
    // einen Chip anzubieten, der woandershin führt.
    expect(ankerTreffer("Wo finde ich die Sitzungstermine?", ANKER)).toEqual([]);
    // Nur Stoppwörter: „die" steht in zwei Titeln, sagt aber nichts.
    expect(ankerTreffer("Wo ist das hier auf der Seite?", ANKER)).toEqual([]);
  });
});

describe("ankerListe", () => {
  function fakeDok(eintraege: [string, string | null][]): Document {
    return {
      querySelectorAll: () => eintraege.map(([key, titel]) => ({
        getAttribute: (n: string) => (n === "data-erklaer" ? key : titel),
      })),
    } as unknown as Document;
  }

  it("sammelt Schlüssel und Titel in Dokumentreihenfolge", () => {
    const dok = fakeDok([["a.eins", "Eins"], ["a.zwei", "Zwei"]]);
    expect(ankerListe(dok)).toEqual([
      { key: "a.eins", titel: "Eins" }, { key: "a.zwei", titel: "Zwei" }]);
  });

  it("lässt titellose Anker aus — ein Schlüssel ist kein Chip-Text", () => {
    expect(ankerListe(fakeDok([["a.eins", null], ["a.zwei", "Zwei"]])))
      .toEqual([{ key: "a.zwei", titel: "Zwei" }]);
  });

  it("behält zwei Bausteine mit demselben Schlüssel, aber eigenem Titel", () => {
    // Genau so steht es auf /haushalt/schulden: zwei Zeitreihen, ein
    // Schlüssel, zwei Titel (gemessen im Browser am 22.09.2026). Eine
    // Entdopplung nur über den Schlüssel hätte die zweite verschluckt.
    const dok = fakeDok([
      ["hh.zeitreihe", "Schulden total"],
      ["hh.zeitreihe", "Verbürgt und selbst geschuldet"],
    ]);
    expect(ankerListe(dok)).toHaveLength(2);
  });

  it("nimmt denselben Baustein nur einmal und deckelt bei 20", () => {
    const viele: [string, string][] = Array.from({ length: 30 },
      (_, i) => [`a.k${i}`, `Titel ${i}`]);
    expect(ankerListe(fakeDok([...viele, ["a.k0", "Titel 0"]]))).toHaveLength(20);
  });

  it("kürzt einen langen Titel auf 80 Zeichen", () => {
    const lang = ankerListe(fakeDok([["a.x", "T".repeat(300)]]))[0];
    expect(lang.titel.length).toBeLessThanOrEqual(82);
  });
});

describe("daumenZeigen — die Lotsen-Runde", () => {
  it("bekommt keinen Daumen: kein Server, kein Modell, nichts zu benoten", () => {
    expect(daumenZeigen({ answer: "Das findest du hier:", mode: "local" })).toBe(false);
  });
});

describe("anschlussfragen", () => {
  const ANKER = [
    { key: "hh.rate", titel: "Rate-Treppe" },
    { key: "hh.zins", titel: "Kredite und Zinsen" },
  ];
  const FERTIG = { answer: "Fünf Sätze.", mode: "explain" as const };

  it("bietet den nächsten Baustein und das erste Fachwort an", () => {
    expect(anschlussfragen(FERTIG, ANKER, new Set(), ["Umschuldung"])).toEqual([
      { art: "anker", anker: ANKER[0] },
      { art: "begriff", begriff: "Umschuldung" },
    ]);
  });

  it("gibt dem Archiv den Vorrang — und deckelt bei zwei", () => {
    // Die Antwort hat weitergereicht: Das ist der dringendste nächste
    // Schritt, das Fachwort fällt dafür heraus.
    expect(anschlussfragen({ ...FERTIG, next: "ratsfrage" }, ANKER, new Set(),
                           ["Umschuldung", "Haushalt"])).toEqual([
      { art: "ratsfrage" },
      { art: "anker", anker: ANKER[0] },
    ]);
  });

  it("wiederholt nichts, was schon gefragt wurde", () => {
    const erklaert = new Set(["hh.rate\u0000Rate-Treppe", "umschuldung"]);
    expect(anschlussfragen(FERTIG, ANKER, erklaert, ["Umschuldung", "Haushalt"]))
      .toEqual([
        { art: "anker", anker: ANKER[1] },
        { art: "begriff", begriff: "Haushalt" },
      ]);
  });

  it("unterscheidet zwei Bausteine mit demselben Schlüssel", () => {
    // Auf /haushalt/schulden tragen zwei Zeitreihen denselben Schlüssel. Wer
    // die erste erklärt bekommen hat, soll die zweite noch angeboten kriegen.
    const zwei = [
      { key: "hh.zeitreihe", titel: "Schulden total" },
      { key: "hh.zeitreihe", titel: "Verbürgt und selbst geschuldet" },
    ];
    expect(anschlussfragen(FERTIG, zwei, new Set(["hh.zeitreihe\u0000Schulden total"]), []))
      .toEqual([{ art: "anker", anker: zwei[1] }]);
  });

  it("schweigt unter einer Fehler-Runde und unter der Lotsen-Runde", () => {
    expect(anschlussfragen({ answer: "Das hat nicht geklappt.", fehler: true },
                           ANKER, new Set(), ["Umschuldung"])).toEqual([]);
    expect(anschlussfragen({ answer: "Das steht hier:", mode: "local" },
                           ANKER, new Set(), ["Umschuldung"])).toEqual([]);
    // Und während der Strom noch läuft, steht noch keine Antwort da.
    expect(anschlussfragen({ answer: "", mode: null }, ANKER, new Set(), [])).toEqual([]);
  });

  it("reicht die Ratsantwort nicht noch einmal ans Archiv weiter", () => {
    expect(anschlussfragen({ answer: "Der Rat hat zugestimmt.", ratsfrage: true,
                            next: "ratsfrage" }, [], new Set(), ["Haushalt"]))
      .toEqual([{ art: "begriff", begriff: "Haushalt" }]);
  });

  it("gibt nichts aus, wo es nichts gibt", () => {
    expect(anschlussfragen(FERTIG, [], new Set(), [])).toEqual([]);
  });
});

describe("chipTitel", () => {
  it("lässt kurze Titel in Ruhe", () => {
    expect(chipTitel("Rate-Treppe")).toBe("Rate-Treppe");
  });

  it("wirft den Stand hinter dem Mittelpunkt weg", () => {
    // Gemessen im Browser (22.09.2026): So heißt die Bühne auf
    // /haushalt/schulden, und als Chip war sie zweizeilig.
    expect(chipTitel("Drei Zählweisen, eine Stadt · Stand 31.12.2024"))
      .toBe("Drei Zählweisen, eine Stadt");
  });

  it("kappt, was auch danach zu lang ist", () => {
    expect(chipTitel("W".repeat(90)).length).toBeLessThanOrEqual(40);
  });
});
