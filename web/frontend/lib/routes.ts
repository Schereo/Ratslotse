// Central URL builders for the auth-gated council detail views.
//
// They use query params (not path segments) so the whole (app) area static-
// exports cleanly for the native app (no dynamic [id]/[slug] routes to enumerate).
// These pages sit behind login, so path-based SEO URLs would add nothing — see
// the sitemap note and next.config.mjs (MOBILE export).
export const decisionHref = (id: number | string) => `/council/decision?id=${id}`;
/** Die KI-Frage als eigene Seite (Split 12.08.): Headliner mit eigener
 *  Adresse. `q` befüllt den Composer vor, `share` öffnet einen geteilten
 *  Antwort-Snapshot. Alt-Links auf /council?mode=fragen leitet die
 *  Council-Seite hierher um. */
export const fragenHref = (opts?: { q?: string; share?: string }) => {
  const p = new URLSearchParams();
  if (opts?.q) p.set("q", opts.q);
  if (opts?.share) p.set("share", opts.share);
  const qs = p.toString();
  return qs ? `/fragen?${qs}` : "/fragen";
};
export const personHref = (slug: string) => `/council/person?slug=${encodeURIComponent(slug)}`;
export const themaHref = (slug: string) => `/council/thema?slug=${encodeURIComponent(slug)}`;
export const ortHref = (id: string) => `/council/ort?id=${encodeURIComponent(id)}`;
/** Quiz-Start, optional mit vorgewähltem Gebiet (z. B. "electoral_district:3"). */
export const quizHref = (area?: string) => (area ? `/quiz?area=${encodeURIComponent(area)}` : "/quiz");
/** Sitzungsliste, aufgeklappt bei einer bestimmten Sitzung (Design 28a/S2:
 *  Ziel des Zurück-Knopfs, wenn es keine History gibt — etwa aus Push oder
 *  geteiltem Link). Die Sitzungen-Ansicht wertet ?ksinr= bereits aus. */
// `tops` nennt die Tagesordnungspunkte, zu denen gesprungen werden soll — die
// Sitzung klappt auf UND die Ansicht rollt zur gemeldeten Zeile. Die Nummern
// gehen vollständig mit („Ö 6", nicht „6"): „Ö 6" und „N 6" sind verschiedene
// Punkte. Spiegelt `sitzung_href` in council/ergebnisse.py.
export const sessionHref = (ksinr: number, tops?: string[]) => {
  const ziel = `/council?tab=sessions&ksinr=${ksinr}`;
  const sauber = (tops ?? []).map((t) => t.trim()).filter(Boolean);
  return sauber.length ? `${ziel}&top=${encodeURIComponent(sauber.join(","))}` : ziel;
};

/** Die eigenständige Sitzungs-Seite — Ziel der Teilen-Knöpfe.
 *
 *  Bewusst ein anderer Pfad als `sessionHref`: Der führt in die Sitzungs*liste*
 *  und verlangt ein Konto (dort stehen Filter, Merkliste und die eigenen
 *  Themen). Ein weitergereichter Link soll dagegen ohne Anmeldung lesbar sein
 *  — „guck mal, was am Donnerstag drankommt" endet sonst im
 *  Registrierungsformular. Diese Seite steht deshalb in
 *  `lib/public-routes.ts::OEFFENTLICHE_PFADE` und holt ihre Tagesordnung vom
 *  ohnehin offenen `/council/session/{ksinr}`.
 *
 *  `tops` reist wie bei `sessionHref` als volle Nummer („Ö 6", nicht „6"): Die
 *  Seite rollt zu dieser Zeile und hebt sie kurz hervor.
 */
export const sitzungHref = (ksinr: number, tops?: string[]) => {
  const ziel = `/council/sitzung?ksinr=${ksinr}`;
  const sauber = (tops ?? []).map((t) => t.trim()).filter(Boolean);
  return sauber.length ? `${ziel}&top=${encodeURIComponent(sauber.join(","))}` : ziel;
};
