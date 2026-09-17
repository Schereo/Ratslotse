import type { ApiAntwort } from "./vertrag";

type MailStats = ApiAntwort<"/admin/stats/emails">;

/** Der Server liefert nur Tage mit Versand. Lücken müssen auf der Zeitachse
 * Platz behalten; der erste und letzte Kalendertag sind Teil-Tage. */
export function mailVerlauf(rows: MailStats["je_tag"], tage: number, heute = new Date().toISOString().slice(0, 10)) {
  const ende = new Date(`${heute}T00:00:00Z`).getTime();
  const nachTag = new Map(rows.map((r) => [r.tag, r.mails]));
  const days = Array.from({ length: tage + 1 }, (_, i) => new Date(ende - (tage - i) * 86400000).toISOString().slice(0, 10));
  return { days, values: days.map((day) => nachTag.get(day) ?? 0) };
}

/** Auch reine Fehlschläge und Link-Aufrufe zu älteren Mails behalten eine
 * eigene Zeile. Aufrufe und Sendungen sind unabhängige Messungen. */
export function mailAnlaesse(data: Pick<MailStats, "je_anlass" | "rueckkehr_je_anlass">) {
  const versand = new Map(data.je_anlass.map((r) => [r.anlass, r]));
  const aufrufe = new Map(data.rueckkehr_je_anlass.map((r) => [r.anlass, r.rueckkehr]));
  return [...new Set([...versand.keys(), ...aufrufe.keys()])].map((anlass) => ({
    anlass, mails: versand.get(anlass)?.mails ?? 0, konten: versand.get(anlass)?.konten ?? 0,
    gescheitert: versand.get(anlass)?.gescheitert ?? 0, rueckkehr: aufrufe.get(anlass) ?? 0,
  }));
}
