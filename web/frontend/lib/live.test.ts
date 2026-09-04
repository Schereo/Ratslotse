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
