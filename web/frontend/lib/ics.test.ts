import { describe, expect, it } from "vitest";
import { buildIcs, type IcsSession } from "./ics";

// Ein .ics wird von keinem Test der Welt geöffnet — es landet in Apple
// Calendar, Google und Outlook. Was dort schiefgeht, meldet niemand zurück:
// Der Termin fehlt einfach, oder er steht zwei Stunden falsch.

const BASIS: IcsSession = {
  uid: "ks-4711",
  committee: "Rat der Stadt Oldenburg",
  session_date: "2026-09-03",
  session_time: "18:00",
  location: "Altes Rathaus, Markt 1",
  url: "https://ratsinfo.oldenburg.de/sitzung/4711",
};

const zeilen = (ics: string) => ics.split("\r\n");
/** Gefaltete Zeilen wieder zusammensetzen — so, wie ein Kalender sie liest. */
const entfalten = (ics: string) => ics.replace(/\r\n /g, "");

describe("Gerüst", () => {
  it("ist ein vollständiger Kalender mit genau einem Termin", () => {
    const ics = buildIcs(BASIS);
    expect(ics.startsWith("BEGIN:VCALENDAR")).toBe(true);
    expect(ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
    expect(ics.match(/BEGIN:VEVENT/g)).toHaveLength(1);
    expect(ics.match(/END:VEVENT/g)).toHaveLength(1);
  });

  it("trennt Zeilen mit CRLF — RFC 5545, nicht mit \\n", () => {
    const ics = buildIcs(BASIS);
    expect(ics).toContain("\r\n");
    expect(ics.replace(/\r\n/g, "")).not.toContain("\n");
  });

  it("bringt die Zeitzone vollständig mit", () => {
    // Nur „TZID=Europe/Berlin" reicht nicht: Ein Kalender, der die Zone nicht
    // kennt, legt den Termin sonst in UTC ab — im Sommer zwei Stunden zu früh.
    const ics = buildIcs(BASIS);
    expect(ics).toContain("BEGIN:VTIMEZONE");
    expect(ics).toContain("TZID:Europe/Berlin");
    expect(ics).toContain("TZOFFSETTO:+0200");   // Sommerzeit
    expect(ics).toContain("TZOFFSETTO:+0100");   // Winterzeit
  });

  it("macht die UID eindeutig über die Domäne", () => {
    expect(buildIcs(BASIS)).toContain("UID:ks-4711@ratslotse.de");
  });
});

describe("Mit Uhrzeit", () => {
  it("setzt Anfang und Ende in der lokalen Zone", () => {
    const ics = entfalten(buildIcs(BASIS));
    expect(ics).toContain("DTSTART;TZID=Europe/Berlin:20260903T180000");
    expect(ics).toContain("DTEND;TZID=Europe/Berlin:20260903T200000");
  });

  it("füllt eine einstellige Stunde auf", () => {
    const ics = entfalten(buildIcs({ ...BASIS, session_time: "9:30" }));
    expect(ics).toContain("DTSTART;TZID=Europe/Berlin:20260903T093000");
    expect(ics).toContain("DTEND;TZID=Europe/Berlin:20260903T113000");
  });

  it("läuft am Tagesende nicht in den nächsten Tag über", () => {
    // 22:00 + 2 h wären 24:00 — das gibt es nicht, und ein Kalender wirft
    // den Termin dann weg.
    const ics = entfalten(buildIcs({ ...BASIS, session_time: "22:00" }));
    expect(ics).toContain("DTEND;TZID=Europe/Berlin:20260903T230000");
  });

  it("sagt in der Beschreibung, dass das Ende geschätzt ist", () => {
    expect(entfalten(buildIcs(BASIS))).toContain("Dauer gesch\\u00e4tzt".replace("\\u00e4", "ä"));
  });
});

describe("Ohne Uhrzeit — Ganztagstermin", () => {
  const ohne = { ...BASIS, session_time: null };

  it("nimmt VALUE=DATE und den Folgetag als Ende", () => {
    // Bei VALUE=DATE ist DTEND exklusiv: Ohne den Folgetag verschwindet der
    // Termin in manchen Kalendern ganz.
    const ics = entfalten(buildIcs(ohne));
    expect(ics).toContain("DTSTART;VALUE=DATE:20260903");
    expect(ics).toContain("DTEND;VALUE=DATE:20260904");
  });

  it("rechnet über die Monatsgrenze", () => {
    const ics = entfalten(buildIcs({ ...ohne, session_date: "2026-09-30" }));
    expect(ics).toContain("DTEND;VALUE=DATE:20261001");
  });

  it("sagt, dass die Uhrzeit noch fehlt", () => {
    expect(entfalten(buildIcs(ohne))).toContain("Uhrzeit noch nicht");
  });

  it("behandelt eine unlesbare Uhrzeit wie gar keine", () => {
    for (const t of ["abends", "", "18", null, undefined]) {
      expect(entfalten(buildIcs({ ...BASIS, session_time: t as never })))
        .toContain("DTSTART;VALUE=DATE:");
    }
  });
});

describe("Maskierung — RFC 5545 §3.3.11", () => {
  it("maskiert Komma und Semikolon im Ort", () => {
    // Unmaskiert zerlegt der Kalender „Markt 1, Oldenburg" in zwei Werte.
    const ics = entfalten(buildIcs({ ...BASIS, location: "Rathaus, Markt 1; EG" }));
    expect(ics).toContain(String.raw`LOCATION:Rathaus\, Markt 1\; EG`);
  });

  it("maskiert den Backslash zuerst — sonst entsteht eine falsche Folge", () => {
    const ics = entfalten(buildIcs({ ...BASIS, committee: "A\\B" }));
    expect(ics).toContain("SUMMARY:A\\\\B");
  });

  it("macht aus einem Zeilenumbruch die Folge \\n", () => {
    const ics = entfalten(buildIcs({ ...BASIS, agenda: ["Erste\nZweite"] }));
    expect(ics).toContain(String.raw`Erste\nZweite`);
    // Der Wert darf keinen ECHTEN Umbruch enthalten. Nach dem Entfalten steht
    // jede Eigenschaft auf genau einer Zeile — die DESCRIPTION also auch.
    const beschreibung = ics.split("\r\n").find((z) => z.startsWith("DESCRIPTION:"));
    expect(beschreibung).toBeDefined();
    expect(beschreibung).toContain(String.raw`Erste\nZweite`);
  });
});

describe("Zeilenfaltung — RFC 5545 §3.1", () => {
  it("bricht lange Zeilen um, Folgezeilen beginnen mit einem Leerzeichen", () => {
    const lang = buildIcs({ ...BASIS, agenda: Array.from({ length: 20 }, (_, i) => `Tagesordnungspunkt Nummer ${i} mit einem recht langen Titel`) });
    const gefaltet = zeilen(lang).filter((z) => z.startsWith(" "));
    expect(gefaltet.length).toBeGreaterThan(0);
  });

  it("hält jede Zeile bei höchstens 75 Oktett", () => {
    // Gemessen in UTF-8-BYTES, nicht in Zeichen: Apple Calendar verschluckt
    // sich sonst an Umlauten kurz vor der Grenze.
    const enc = new TextEncoder();
    const ics = buildIcs({
      ...BASIS,
      committee: "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit",
      agenda: ["Größenänderung der Grünflächen an der Straße für Fußgänger und Radfahrende"],
    });
    for (const z of zeilen(ics)) {
      expect(enc.encode(z).length).toBeLessThanOrEqual(75);
    }
  });

  it("zerschneidet kein Zeichen — der Text kommt vollständig wieder an", () => {
    const titel = "Grünflächenänderung Öffentlichkeitsbeteiligung Straßenausbaubeiträge";
    const ics = buildIcs({ ...BASIS, agenda: [titel] });
    expect(entfalten(ics)).toContain(titel);
  });
});

describe("Optionales bleibt weg, statt leer dazustehen", () => {
  it("ohne Ort keine LOCATION-Zeile", () => {
    expect(entfalten(buildIcs({ ...BASIS, location: null }))).not.toContain("LOCATION:");
  });

  it("ohne Adresse keine URL-Zeile", () => {
    const ics = entfalten(buildIcs({ ...BASIS, url: null }));
    expect(ics).not.toContain("\r\nURL:");
    expect(ics).not.toContain("Ratsinfo:");
  });
});
