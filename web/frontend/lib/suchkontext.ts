/** Eine Suchadresse beschreibt die ganze Ergebnisliste. Der Tab-Speicher ist
 *  nur die Abkürzung beim erneuten Öffnen von „Suche“, nie ein Zusatzfilter
 *  für einen geteilten Link. `page=1` unterscheidet eine explizit ungefilterte
 *  Suche vom bloßen Navigationseinstieg /council. */
const FILTER = [
  "q", "committee", "outcome", "sort", "field", "party", "district",
  "location", "location_name", "date_from", "date_to", "cat", "subvotes", "topic",
] as const;
const LETZTE = "ratslotse:suche:adresse";
const POSITIONEN = "ratslotse:suche:positionen";
// Nur der laufende Tab kennt seine direkte Navigation. sessionStorage wird
// in neue Tabs kopiert; history.length zählt außerdem Vorwärts-Einträge.
let direktGeoeffnet: string | null = null;
export const kamDirektAusSuche = (detail: string) => direktGeoeffnet === detail;

export function suchAdresse(roh: string): string {
  const eingang = new URLSearchParams(roh);
  const p = new URLSearchParams({ tab: "decisions" });
  for (const key of FILTER) {
    const wert = eingang.get(key);
    if (wert) p.set(key, wert);
  }
  const seite = Number(eingang.get("page"));
  p.set("page", String(Number.isSafeInteger(seite) && seite > 0 ? seite : 1));
  return `/council?${p}`;
}

export function aendereSuche(roh: string, werte: Record<string, string>): string {
  const p = new URLSearchParams(roh);
  p.set("page", "1");
  for (const [key, wert] of Object.entries(werte)) {
    if (wert) p.set(key, wert); else p.delete(key);
  }
  return suchAdresse(p.toString());
}

export function istSucheinstieg(roh: string): boolean {
  const p = new URLSearchParams(roh);
  return [...p.keys()].every((key) => key === "tab")
    && (!p.has("tab") || p.get("tab") === "decisions");
}

/** Ein URL-Parameter darf ausschließlich in unsere Beschluss-Suche führen. */
export function suchRueckweg(roh: string | null): string | null {
  if (!roh?.startsWith("/") || roh.startsWith("//")) return null;
  try {
    const u = new URL(roh, "https://ratslotse.invalid");
    if (u.origin !== "https://ratslotse.invalid" || u.pathname.replace(/\/$/, "") !== "/council") return null;
    if (u.searchParams.has("tab") && u.searchParams.get("tab") !== "decisions") return null;
    const hash = /^#beschluss-\d+$/.test(u.hash) ? u.hash : "";
    return suchAdresse(u.search) + hash;
  } catch { return null; }
}

export function merkeSuche(href: string): void {
  try { sessionStorage.setItem(LETZTE, href); } catch { /* privater Modus */ }
}

export function letzteSuche(): string | null {
  try { return suchRueckweg(sessionStorage.getItem(LETZTE)); } catch { return null; }
}

export type SuchPosition = {
  href: string;
  treffer: string;
  oben: number;
  detail: string;
};

function positionen(): SuchPosition[] {
  try {
    const roh: unknown = JSON.parse(sessionStorage.getItem(POSITIONEN) ?? "[]");
    if (!Array.isArray(roh)) return [];
    return roh.filter((p): p is SuchPosition => p && typeof p.href === "string"
      && typeof p.treffer === "string" && /^beschluss-\d+$/.test(p.treffer)
      && Number.isFinite(p.oben)
      && typeof p.detail === "string");
  } catch { return []; }
}

export function merkeSuchPosition(position: SuchPosition): void {
  direktGeoeffnet = position.detail;
  try {
    sessionStorage.setItem(POSITIONEN, JSON.stringify([
      position, ...positionen().filter((p) => p.href !== position.href),
    ].slice(0, 12)));
  } catch { /* Die Adresse funktioniert auch ohne Speicher. */ }
}

export function suchPosition(href: string): SuchPosition | undefined {
  return positionen().find((p) => p.href === href.split("#")[0]);
}
