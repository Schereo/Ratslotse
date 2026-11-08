import type { ApiAntwort } from "@/lib/vertrag";

export type ViertelTafel = ApiAntwort<"/districts/{place_id}/projects">;

/** Gemeinsame Beschriftungen für Karte und Heute. */
export const STAND: Record<string, { label: string; color: "amber" | "green" | "blue" | "slate" | "red"; rang: number }> = {
  building: { label: "Im Bau", color: "amber", rang: 0 },
  decided: { label: "Beschlossen", color: "green", rang: 1 },
  planning: { label: "In Planung", color: "blue", rang: 2 },
  idea: { label: "Idee", color: "slate", rang: 3 },
  done: { label: "Fertig", color: "slate", rang: 4 },
  rejected: { label: "Abgelehnt", color: "red", rang: 5 },
};

/** Kurzform des abgeleiteten Zustands für Zeile und Badge. Ob ein Vorhaben
 *  so heißt, entscheidet der Server (`council/viertel_zeitplan.py`); hier
 *  steht nur, wie es heißt. Der ganze Satz kommt als `schedule_note`. */
export const ZEITPLAN: Record<string, string> = {
  likely_done: "vermutlich abgeschlossen",
  overdue: "Zeitplan überschritten",
  quiet: "lange kein Beschluss",
};

/** Der Weg eines Vorhabens, kurz beschriftet für die Mini-Grafik auf Heute.
 * „Abgelehnt" liegt neben dem Weg, nicht auf ihm. */
export const WEG_SCHRITTE = [
  { stage: "idea", label: "Idee" },
  { stage: "planning", label: "Planung" },
  { stage: "decided", label: "Beschluss" },
  { stage: "building", label: "Bau" },
  { stage: "done", label: "Fertig" },
] as const;

/** Index der erreichten Stufe auf dem Weg, -1 für „abgelehnt" und Unbekanntes. */
export function wegStufe(stage: string) {
  return WEG_SCHRITTE.findIndex(s => s.stage === stage);
}

/** Ratsdatum statt Erstellungs-/Indexdatum: ein neu berechneter Registereintrag
 * ist keine neue Entwicklung im Viertel. Abgelehnte Vorhaben bleiben relevant,
 * wenn sie die jüngste Beratung sind. Die jüngste Beratung zuerst. */
export function viertelVorhaben(projects: ViertelTafel["projects"]) {
  return projects.filter(p => !p.hidden).sort((a, b) =>
    (b.last_date ?? b.first_date ?? "").localeCompare(a.last_date ?? a.first_date ?? "") || a.id - b.id,
  );
}

export function letzterViertelStand(projects: ViertelTafel["projects"]) {
  return viertelVorhaben(projects)[0];
}

/** Heute ist ein Ausblick auf die nächsten zwei Wochen, kein Sitzungsarchiv. */
export function naechsteViertelBeratung(upcoming: ViertelTafel["upcoming"], heuteIso: string) {
  // useHeute setzt das lokale Datum erst nach dem Mount. Bei Rücknavigation
  // liegen die Vierteldaten bereits im Cache, bevor dieser Effekt läuft.
  if (!heuteIso) return undefined;
  const grenze = new Date(heuteIso + "T12:00:00Z");
  grenze.setUTCDate(grenze.getUTCDate() + 14);
  const bis = grenze.toISOString().slice(0, 10);
  return upcoming.filter(p => p.session_date >= heuteIso && p.session_date <= bis).sort((a, b) =>
    a.session_date.localeCompare(b.session_date) || (a.session_time ?? "").localeCompare(b.session_time ?? "") || a.id - b.id,
  )[0];
}
