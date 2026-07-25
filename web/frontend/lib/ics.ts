// Sitzungstermin als .ics (Design 28a/W2) — rein client-seitig, kein Endpoint.
//
// Das Ratsinformationssystem kennt keinen Kalender-Export; wer eine Sitzung
// nicht verpassen will, tippt den Termin bisher von Hand ab. Die Daten liegen
// in der Liste ohnehin vor, es fehlte nur das Dateiformat drumherum.

export type IcsSession = {
  uid: string;
  committee: string;
  session_date: string; // ISO yyyy-mm-dd
  session_time?: string | null; // "16:00" — fehlt bei nur terminierten Sitzungen
  location?: string | null;
  url?: string | null;
  /** Tagesordnungspunkte für das Beschreibungsfeld (bereits gekürzt). */
  agenda?: string[];
};

/** Die Sitzung dauert im Ratsinfo nirgends „bis" — zwei Stunden sind die
 *  ehrlichste Annahme; der Vermerk in der Beschreibung sagt es dazu. */
const DEFAULT_HOURS = 2;

// Vollständige Zonendefinition statt bloßem TZID: Ein Kalender, der
// Europe/Berlin nicht kennt, legt den Termin sonst in UTC ab — im Sommer zwei
// Stunden zu früh.
const VTIMEZONE = [
  "BEGIN:VTIMEZONE",
  "TZID:Europe/Berlin",
  "BEGIN:DAYLIGHT",
  "TZOFFSETFROM:+0100",
  "TZOFFSETTO:+0200",
  "TZNAME:CEST",
  "DTSTART:19700329T020000",
  "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
  "END:DAYLIGHT",
  "BEGIN:STANDARD",
  "TZOFFSETFROM:+0200",
  "TZOFFSETTO:+0100",
  "TZNAME:CET",
  "DTSTART:19701025T030000",
  "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
  "END:STANDARD",
  "END:VTIMEZONE",
];

/** RFC 5545 §3.3.11: Komma, Semikolon, Backslash und Zeilenumbrüche maskieren. */
function esc(s: string): string {
  return s
    .replace(/\\/g, "\\\\")
    .replace(/\r?\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

/** RFC 5545 §3.1: Zeilen über 75 Oktett umbrechen (Folge-Zeile beginnt mit
 *  einem Leerzeichen). Apple Calendar verschluckt sich sonst an langen
 *  Tagesordnungen. Gemessen wird in UTF-8-Bytes, nicht in Zeichen. */
function fold(line: string): string {
  const enc = new TextEncoder();
  if (enc.encode(line).length <= 75) return line;
  const out: string[] = [];
  let cur = "";
  let curLen = 0;
  for (const ch of line) {
    const n = enc.encode(ch).length;
    // Erste Zeile 75, Folgezeilen 74 (ein Oktett geht fürs Leerzeichen drauf).
    if (curLen + n > (out.length === 0 ? 75 : 74)) {
      out.push(cur);
      cur = "";
      curLen = 0;
    }
    cur += ch;
    curLen += n;
  }
  if (cur) out.push(cur);
  return out.join("\r\n ");
}

const stamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

export function buildIcs(s: IcsSession): string {
  const day = s.session_date.slice(0, 10).replace(/-/g, "");
  const time = /^\d{1,2}:\d{2}/.test(s.session_time ?? "") ? (s.session_time as string) : null;

  const when: string[] = [];
  if (time) {
    const [h, m] = time.split(":");
    const start = `${day}T${h.padStart(2, "0")}${m}00`;
    const endH = String(Math.min(Number(h) + DEFAULT_HOURS, 23)).padStart(2, "0");
    when.push(`DTSTART;TZID=Europe/Berlin:${start}`, `DTEND;TZID=Europe/Berlin:${day}T${endH}${m}00`);
  } else {
    // Ohne Uhrzeit („Tagesordnung folgt") ein Ganztagstermin — DTEND ist bei
    // VALUE=DATE exklusiv, also der Folgetag.
    const next = new Date(`${s.session_date.slice(0, 10)}T12:00:00`);
    next.setDate(next.getDate() + 1);
    when.push(`DTSTART;VALUE=DATE:${day}`, `DTEND;VALUE=DATE:${stamp(next).slice(0, 8)}`);
  }

  const beschreibung = [
    s.agenda?.length ? `Tagesordnung:\n${s.agenda.map((a) => `• ${a}`).join("\n")}` : "",
    time ? `Dauer geschätzt — im Ratsinformationssystem ist kein Ende hinterlegt.` : "Uhrzeit noch nicht veröffentlicht.",
    s.url ? `Ratsinfo: ${s.url}` : "",
    "Eingetragen über ratslotse.de",
  ]
    .filter(Boolean)
    .join("\n\n");

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Ratslotse//Sitzungstermine//DE",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    ...VTIMEZONE,
    "BEGIN:VEVENT",
    `UID:${esc(s.uid)}@ratslotse.de`,
    `DTSTAMP:${stamp(new Date())}`,
    ...when,
    `SUMMARY:${esc(s.committee)}`,
    s.location ? `LOCATION:${esc(s.location)}` : "",
    `DESCRIPTION:${esc(beschreibung)}`,
    s.url ? `URL:${esc(s.url)}` : "",
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean);

  return lines.map(fold).join("\r\n") + "\r\n";
}

/** Datei anbieten: In der App über das Teilen-Blatt (dort greift „Zu Kalender
 *  hinzufügen"), im Browser als Download. Beides ohne zusätzliches Plugin. */
export async function offerIcs(s: IcsSession, filename: string): Promise<void> {
  const text = buildIcs(s);
  const file = new File([text], filename, { type: "text/calendar" });

  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: s.committee });
      return;
    } catch (e) {
      if ((e as Error).name === "AbortError") return; // Blatt geschlossen
      /* Teilen blockiert → Download versuchen */
    }
  }

  const url = URL.createObjectURL(new Blob([text], { type: "text/calendar;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
