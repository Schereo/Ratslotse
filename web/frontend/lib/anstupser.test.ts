import { describe, expect, it } from "vitest";

import {
  darfAnstupsen, GRENZEN, imFenster, LEER, nachAnzeige, nachJa, nachNein,
  type AnstupserKontext, type AnstupserStand,
} from "./anstupser";

const TAG = 86_400_000;
const JETZT = Date.UTC(2026, 8, 21, 12, 0, 0);

/** Ein Moment, in dem Lotti anklopfen DARF — jede Prüfung verdirbt genau einen Wert. */
const GUT: AnstupserKontext = {
  seiteErlaubt: true,
  lesezeitMs: 60_000,
  seitInteraktionMs: 2_000,
  seitenInSitzung: 5,
  fensterWarOffen: false,
  heuteBenutzt: false,
  beschaeftigt: false,
};

const stand = (p: Partial<AnstupserStand> = {}): AnstupserStand => ({ ...LEER, ...p });

describe("darfAnstupsen", () => {
  it("klopft im guten Moment an", () => {
    expect(darfAnstupsen(stand(), GUT, JETZT)).toBe(true);
  });

  it("schweigt auf Seiten, die es nicht erlauben", () => {
    // `/fragen` etwa: Dort ist der Composer der Weg, und eine Blase daneben
    // wäre eine zweite Aufforderung zu derselben Sache.
    expect(darfAnstupsen(stand(), { ...GUT, seiteErlaubt: false }, JETZT)).toBe(false);
  });

  it("schweigt, solange jemand tippt oder markiert", () => {
    expect(darfAnstupsen(stand(), { ...GUT, beschaeftigt: true }, JETZT)).toBe(false);
  });

  it("schweigt in den ersten beiden Seitenaufrufen einer Sitzung", () => {
    expect(darfAnstupsen(stand(), { ...GUT, seitenInSitzung: 1 }, JETZT)).toBe(false);
    expect(darfAnstupsen(stand(), { ...GUT, seitenInSitzung: 2 }, JETZT)).toBe(false);
    expect(darfAnstupsen(stand(), { ...GUT, seitenInSitzung: 3 }, JETZT)).toBe(true);
  });

  it("wartet die Lesezeit ab", () => {
    expect(darfAnstupsen(stand(), { ...GUT, lesezeitMs: GRENZEN.lesezeitMs - 1 }, JETZT)).toBe(false);
    expect(darfAnstupsen(stand(), { ...GUT, lesezeitMs: GRENZEN.lesezeitMs }, JETZT)).toBe(true);
  });

  it("schweigt, wenn lange nichts passiert ist — dann ist niemand da", () => {
    // 45 Sekunden „Lesezeit" hat auch ein Tab, der offen liegengeblieben ist.
    expect(darfAnstupsen(stand(), { ...GUT, seitInteraktionMs: 60_000 }, JETZT)).toBe(false);
  });

  it("schweigt, wenn das Fenster in dieser Sitzung schon offen war", () => {
    expect(darfAnstupsen(stand(), { ...GUT, fensterWarOffen: true }, JETZT)).toBe(false);
  });

  it("schweigt, wenn Lotti heute schon benutzt wurde", () => {
    expect(darfAnstupsen(stand(), { ...GUT, heuteBenutzt: true }, JETZT)).toBe(false);
  });

  it("klopft höchstens einmal am Tag an", () => {
    expect(darfAnstupsen(stand({ zuletzt: JETZT - 3 * 3600_000 }), GUT, JETZT)).toBe(false);
    expect(darfAnstupsen(stand({ zuletzt: JETZT - 25 * 3600_000 }), GUT, JETZT)).toBe(true);
  });

  it("klopft höchstens dreimal in 30 Tagen an", () => {
    const drei = [JETZT - 20 * TAG, JETZT - 10 * TAG, JETZT - 2 * TAG];
    expect(darfAnstupsen(stand({ tage30: drei }), GUT, JETZT)).toBe(false);
    // Fällt der älteste aus dem Fenster, ist wieder Platz.
    const alt = [JETZT - 40 * TAG, JETZT - 10 * TAG, JETZT - 2 * TAG];
    expect(darfAnstupsen(stand({ tage30: alt }), GUT, JETZT)).toBe(true);
  });

  it("macht nach zwei Ablehnungen zwei Monate Pause", () => {
    const abgelehnt = stand({ abgelehnt: 2, zuletzt: JETZT - 30 * TAG });
    expect(darfAnstupsen(abgelehnt, GUT, JETZT)).toBe(false);
    expect(darfAnstupsen({ ...abgelehnt, zuletzt: JETZT - 61 * TAG }, GUT, JETZT)).toBe(true);
  });

  it("macht nach einem Ja zwei Wochen Pause", () => {
    expect(darfAnstupsen(stand({ angenommen: JETZT - 3 * TAG }), GUT, JETZT)).toBe(false);
    expect(darfAnstupsen(stand({ angenommen: JETZT - 15 * TAG }), GUT, JETZT)).toBe(true);
  });
});

describe("der Stand danach", () => {
  it("merkt sich die Anzeige — und vergisst, was älter als 30 Tage ist", () => {
    const vorher = stand({ tage30: [JETZT - 40 * TAG, JETZT - 5 * TAG] });
    const nachher = nachAnzeige(vorher, JETZT);
    expect(nachher.zuletzt).toBe(JETZT);
    expect(nachher.tage30).toEqual([JETZT - 5 * TAG, JETZT]);
  });

  it("setzt den Ablehnungs-Zähler nach einem Ja zurück", () => {
    expect(nachJa(stand({ abgelehnt: 2 }), JETZT)).toMatchObject({ abgelehnt: 0, angenommen: JETZT });
  });

  it("zählt ein × mit", () => {
    expect(nachNein(stand({ abgelehnt: 1 })).abgelehnt).toBe(2);
  });

  it("imFenster wirft alte Zeitpunkte weg", () => {
    expect(imFenster([JETZT - 31 * TAG, JETZT - 29 * TAG], JETZT)).toEqual([JETZT - 29 * TAG]);
  });
});
