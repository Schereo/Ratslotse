// Central URL builders for the auth-gated council detail views.
//
// They use query params (not path segments) so the whole (app) area static-
// exports cleanly for the native app (no dynamic [id]/[slug] routes to enumerate).
// These pages sit behind login, so path-based SEO URLs would add nothing — see
// the sitemap note and next.config.mjs (MOBILE export).
export const decisionHref = (id: number | string) => `/council/decision?id=${id}`;
export const personHref = (slug: string) => `/council/person?slug=${encodeURIComponent(slug)}`;
export const themaHref = (slug: string) => `/council/thema?slug=${encodeURIComponent(slug)}`;
/** Quiz-Start, optional mit vorgewähltem Gebiet (z. B. "wahlbereich:3"). */
export const quizHref = (area?: string) => (area ? `/quiz?area=${encodeURIComponent(area)}` : "/quiz");
/** Sitzungsliste, aufgeklappt bei einer bestimmten Sitzung (Design 28a/S2:
 *  Ziel des Zurück-Knopfs, wenn es keine History gibt — etwa aus Push oder
 *  geteiltem Link). Die Sitzungen-Ansicht wertet ?ksinr= bereits aus. */
export const sessionHref = (ksinr: number) => `/council?tab=sessions&ksinr=${ksinr}`;
