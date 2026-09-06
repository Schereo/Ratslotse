import { describe, expect, it } from "vitest";
import {
  currentSession,
  currentSessionToday,
  isLive,
  isLiveNow,
  runningTimeText,
  timeOnDay,
} from "./live";

// Das Live-Fenster ist die Logik hinter dem roten „Live"-Band über der
// Sitzung. Sie ist reine Rechnerei auf einer Uhrzeit — und genau deshalb im
// Browsertest nicht prüfbar: Den Fall „16:29 gegen 16:30" kann man dort nicht
// herstellen, ohne die Systemuhr zu stellen.
//
// Der Ratstag ist der harte Fall, und er ist echt (03.09.2026): Um 16:00
// beginnt der Ausschuss für allgemeine Angelegenheiten, um 16:30 der
// Verwaltungsausschuss, um 18:00 der Rat. Das Band darf zu keiner Minute zwei
// Sitzungen zeigen und zu keiner Minute keine.

const uhr = (hhmm: string) => new Date(`2026-09-03T${hhmm}:00`);

const AUSSCHUSS = { session_time: "16:00", live_until: "16:30", committee: "Ausschuss für allgemeine Angelegenheiten" };
const VERWALTUNG = { session_time: "16:30", live_until: "18:00", committee: "Verwaltungsausschuss" };
const RAT = { session_time: "18:00", live_until: null, committee: "Rat der Stadt Oldenburg" };

describe("isLive — das Fenster einer Sitzung", () => {
  it("beginnt auf die Minute genau", () => {
    expect(isLive(AUSSCHUSS, uhr("15:59"))).toBe(false);
    expect(isLive(AUSSCHUSS, uhr("16:00"))).toBe(true);
  });

  it("endet an der Startzeit der nächsten — ohne Lücke, ohne Überlappung", () => {
    // Der Grund für `live_until`: Ohne das Feld liefe der Ausschuss über
    // seinen Deckel bis 19:00 weiter und stünde neben dem Rat im Band.
    expect(isLive(AUSSCHUSS, uhr("16:29"))).toBe(true);
    expect(isLive(AUSSCHUSS, uhr("16:30"))).toBe(false);
    expect(isLive(VERWALTUNG, uhr("16:30"))).toBe(true);
  });

  it("deckelt ohne `live_until` bei drei Stunden — beim Rat bei vier", () => {
    const fachausschuss = { session_time: "18:00", live_until: null, committee: "Bauausschuss" };
    expect(isLive(fachausschuss, uhr("21:00"))).toBe(true);
    expect(isLive(fachausschuss, uhr("21:01"))).toBe(false);
    expect(isLive(RAT, uhr("21:01"))).toBe(true);
    expect(isLive(RAT, uhr("22:00"))).toBe(true);
    expect(isLive(RAT, uhr("22:01"))).toBe(false);
  });

  it("ignoriert ein `live_until`, das vor dem Beginn liegt", () => {
    // Kaputte Daten dürfen das Band nicht dauerhaft ausblenden: Dann greift
    // wieder der Deckel.
    const krumm = { session_time: "18:00", live_until: "09:00", committee: "Bauausschuss" };
    expect(isLive(krumm, uhr("19:00"))).toBe(true);
  });

  it("zeigt ohne Startzeit gar nichts", () => {
    expect(isLive({ session_time: null, live_until: null, committee: "Rat" }, uhr("18:00"))).toBe(false);
  });
});

describe("currentSession — höchstens eine, und zwar die richtige", () => {
  const alle = [AUSSCHUSS, VERWALTUNG, RAT];

  it.each([
    ["16:15", AUSSCHUSS],
    ["16:30", VERWALTUNG],
    ["17:59", VERWALTUNG],
    ["18:00", RAT],
    ["21:30", RAT],
  ])("um %s läuft die erwartete Sitzung", (zeit, erwartet) => {
    expect(currentSession(alle, uhr(zeit as string))).toBe(erwartet);
  });

  it("nimmt bei Überlappung die zuletzt begonnene", () => {
    // Kommt vor, wenn `live_until` fehlt (ältere Antwort aus dem Cache):
    // Dann laufen nach dem Deckel zwei gleichzeitig, und die spätere hat die
    // frühere abgelöst.
    const ohne = [
      { session_time: "16:00", live_until: null, committee: "Ausschuss" },
      { session_time: "16:30", live_until: null, committee: "Verwaltungsausschuss" },
    ];
    expect(currentSession(ohne, uhr("17:00"))?.committee).toBe("Verwaltungsausschuss");
  });

  it("liefert nichts bei leerer oder fehlender Liste", () => {
    expect(currentSession([], uhr("17:00"))).toBeUndefined();
    expect(currentSession(undefined, uhr("17:00"))).toBeUndefined();
  });
});

describe("isLiveNow / currentSessionToday — das Datum zählt mit", () => {
  it("eine Sitzung von gestern läuft nie, auch zur selben Uhrzeit", () => {
    const gestern = { session_date: "2026-09-02", ...AUSSCHUSS };
    expect(isLiveNow(gestern, uhr("16:15"))).toBe(false);
    expect(isLiveNow({ session_date: "2026-09-03", ...AUSSCHUSS }, uhr("16:15"))).toBe(true);
  });

  it("verträgt ein Datum mit Zeitanteil", () => {
    expect(isLiveNow({ session_date: "2026-09-03T00:00:00", ...AUSSCHUSS }, uhr("16:15"))).toBe(true);
  });

  it("sucht nur unter den heutigen", () => {
    const liste = [
      { session_date: "2026-09-02", ...RAT },
      { session_date: "2026-09-03", ...AUSSCHUSS },
    ];
    expect(currentSessionToday(liste, uhr("16:15"))?.committee).toContain("allgemeine");
  });
});

describe("runningTimeText — kurz genug für eine Zeile", () => {
  it.each([
    ["16:01", "1 Minute"],
    ["16:07", "7 Minuten"],
    ["16:59", "59 Minuten"],
    ["17:00", "1 Stunde"],
    ["18:30", "2,5 Stunden"],
    ["19:00", "3 Stunden"],
  ])("um %s: %s", (zeit, erwartet) => {
    expect(runningTimeText("16:00", uhr(zeit as string))).toBe(erwartet);
  });

  it("bleibt bei einer Uhr, die vor dem Beginn steht, bei null", () => {
    expect(runningTimeText("16:00", uhr("15:00"))).toBe("0 Minuten");
  });
});

describe("timeOnDay", () => {
  it("legt die Uhrzeit auf den Tag von `now`", () => {
    expect(timeOnDay("16:30", uhr("09:00"))?.toISOString())
      .toBe(new Date("2026-09-03T16:30:00").toISOString());
  });

  it("liefert null für leer und unlesbar", () => {
    expect(timeOnDay(null, uhr("09:00"))).toBeNull();
    expect(timeOnDay("", uhr("09:00"))).toBeNull();
    expect(timeOnDay("abends", uhr("09:00"))).toBeNull();
  });
});

// ------------------------------------------------------------------ Live-Stand

import { liveAgoText, liveItemKeys, liveSpeakerText, liveStateFresh, liveTopLabel, partyShort } from "./live";

const STAND = {
  item_number: "9.3", item_title: "Radweg", block_start: null, phase: "aussprache",
  speaker: "Susanne Drügemöller", party: "Bündnis 90/Die Grünen",
  since: "2026-09-03T18:12:00+02:00", as_of: "2026-09-03T18:20:00+02:00",
  updated_at: "2026-09-03T18:20:30+02:00", finished: false,
};

describe("Live-Stand aus der Übertragung", () => {
  it("benennt den laufenden Punkt — als Block, wenn mehrere durchliefen", () => {
    expect(liveTopLabel(STAND)).toBe("TOP 9.3");
    expect(liveTopLabel({ ...STAND, block_start: "9.1" })).toBe("TOP 9.1–9.3");
    expect(liveTopLabel({ ...STAND, block_start: "9.3" })).toBe("TOP 9.3");
    expect(liveTopLabel({ ...STAND, item_number: null })).toBeNull();
  });

  it("kürzt die Fraktion in der Sprecherzeile", () => {
    expect(liveSpeakerText(STAND)).toBe("Susanne Drügemöller (Grüne) spricht");
    expect(liveSpeakerText({ ...STAND, party: null })).toBe("Susanne Drügemöller spricht");
    expect(liveSpeakerText({ ...STAND, speaker: null })).toBeNull();
    expect(partyShort("Die Linke")).toBe("Linke");
    expect(partyShort("Verwaltung")).toBe("Verwaltung");
  });

  it("rechnet den Verzug gegen die eigene Uhr, nie negativ", () => {
    expect(liveAgoText(STAND.as_of, new Date("2026-09-03T18:22:30+02:00"))).toBe("vor 2 Min.");
    expect(liveAgoText(STAND.as_of, new Date("2026-09-03T18:20:20+02:00"))).toBe("gerade eben");
    expect(liveAgoText(STAND.as_of, new Date("2026-09-03T18:19:00+02:00"))).toBe("gerade eben");
    expect(liveAgoText("kaputt")).toBe("");
  });

  it("hält einen Stand nach 20 Minuten Stille für abgebrochen", () => {
    expect(liveStateFresh(STAND, new Date("2026-09-03T18:39:00+02:00"))).toBe(true);
    expect(liveStateFresh(STAND, new Date("2026-09-03T18:41:00+02:00"))).toBe(false);
    expect(liveStateFresh({ ...STAND, finished: true }, new Date("2026-09-03T18:21:00+02:00"))).toBe(false);
  });

  it("markiert in der Tagesordnung den Punkt — oder den ganzen Block", () => {
    const keys = ["1", "2", "9.1", "9.2", "9.3", "9.4"];
    expect([...liveItemKeys(STAND, keys)]).toEqual(["9.3"]);
    expect([...liveItemKeys({ ...STAND, block_start: "9.1" }, keys)]).toEqual(["9.1", "9.2", "9.3"]);
    // Unbekannte Nummer (Dringlichkeitsantrag ohne Zeile): nur sie selbst.
    expect([...liveItemKeys({ ...STAND, item_number: "DZT 1" }, keys)]).toEqual(["DZT 1"]);
    expect(liveItemKeys(null, keys).size).toBe(0);
  });
});
