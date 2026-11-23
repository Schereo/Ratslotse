/**
 * Die Unterseiten der Analyse — EINE Liste für zwei Bauformen.
 *
 * Am Schreibtisch stehen sie als Untermenü in der Seitenleiste
 * (`components/nav.tsx`), auf Telefon und iPad als Reiterleiste oben auf der
 * Seite (`components/analyse-reiter.tsx`). Beide zeigten dieselben Ziele mit
 * denselben Namen, also dürfen sie nicht zwei Listen führen: Ein Reiter, der
 * nur in einer steht, wäre auf dem anderen Gerät unauffindbar.
 *
 * Ohne React und ohne Symbole, damit die Navigation — sie steht auf jeder
 * Seite — nur diese paar Zeilen mitnimmt.
 */

/** Der Unterreiter in der Adresse (`?sub=`). Die Werte sind Adressen und
 *  bleiben deshalb, wie sie sind: Mails, geteilte Links und die App kennen sie. */
export type AnalysisSub = "parties" | "trends" | "ziele" | "personen";

/** Zwei Ziele mehr, als die Analyse-Seite selbst kennt: Sie liegen auf eigenen
 *  Seiten, gehören aber in dieselbe Reihe (Tims Entscheidungen 23.09. und
 *  03.10.2026 — kein eigener Punkt in der Navigation). */
export type AnalysisSection = AnalysisSub | "staedte" | "wahlen";

export type AnalysisFlags = {
  /** Schalter `plaene`: „Pläne" statt „Ziele", unter derselben Adresse. */
  plans: boolean;
  /** Schalter `ideen-anderswo`. */
  ideas: boolean;
  /** Schalter `wahlabend` — die Zielseite `/wahlen` hängt daran. */
  elections: boolean;
};

export type AnalysisSectionItem = { key: AnalysisSection; label: string; href: string };

/** Der Unterreiter aus `?sub=` — alles Unbekannte ist „Trends". */
export function analysisSub(raw: string | null): AnalysisSub {
  return raw === "parties" || raw === "ziele" || raw === "personen" ? raw : "trends";
}

/** Wohin ein Ziel führt. „Trends" ist die Analyse ohne `sub` — dieselbe
 *  Adresse wie der Navigationspunkt selbst. */
export function analysisSectionHref(key: AnalysisSection): string {
  if (key === "staedte") return "/council/ideen";
  if (key === "wahlen") return "/wahlen";
  return key === "trends" ? "/council?tab=analysis" : `/council?tab=analysis&sub=${key}`;
}

/** Die Ziele in Anzeige-Reihenfolge. Trends zuerst: Die Themenfeld-Rückblicke
 *  sind der zugänglichste Einstieg, Parteien und Personen die Vertiefung.
 *
 *  „Finanzen" stand hier bis 11/2026 — Summen aus Beschlusstexten neben dem
 *  echten Haushalt, der dasselbe besser beantwortet (Tim, 09.11.2026). */
export function analysisSections(flags: AnalysisFlags): AnalysisSectionItem[] {
  const keys: [AnalysisSection, string][] = [
    ["trends", "Trends"],
    ["parties", "Parteien"],
    ["personen", "Personen"],
    ["ziele", flags.plans ? "Pläne" : "Ziele"],
  ];
  if (flags.ideas) keys.push(["staedte", "Ideen aus anderen Städten"]);
  if (flags.elections) keys.push(["wahlen", "Wahlen"]);
  return keys.map(([key, label]) => ({ key, label, href: analysisSectionHref(key) }));
}

/** Detailseiten, die zu einem der Ziele gehören: Man kommt über diesen Reiter
 *  hin, also zeigt die Seitenleiste ihn dort als Standort. */
const DETAIL_SECTION: [string, AnalysisSection][] = [
  ["/council/ideen", "staedte"],
  ["/council/person", "personen"],
  // „Der neue Rat" hängt als Hinweis am Reiter Personen und an den Profilen.
  ["/council/neuer-rat", "personen"],
  ["/council/plan", "ziele"],
  ["/wahlen", "wahlen"],
  ["/wahlabend", "wahlen"],
];

/** Welches Ziel gerade offen ist — `null`, wenn die Seite gar nicht zur
 *  Analyse gehört. `pathname` ohne Schluss-Schrägstrich (`pfad()`), `tab` und
 *  `sub` roh aus der Adresse. */
export function activeAnalysisSection(
  pathname: string, tab: string | null, sub: string | null,
): AnalysisSection | null {
  const detail = DETAIL_SECTION.find(([p]) => pathname === p || pathname.startsWith(p + "/"));
  if (detail) return detail[1];
  return pathname === "/council" && tab === "analysis" ? analysisSub(sub) : null;
}
