"use client";

/**
 * Die Reiterleiste der Analyse — in einer eigenen Datei, weil sie auf ZWEI
 * Seiten steht: im Analyse-Reiter von `/council` und auf `/council/ideen`.
 *
 * Bis 11/2026 lag sie in `council-analysis.tsx`, und die Ideen-Seite zog mit
 * diesem einen Import den Code aller Analyse-Ansichten mit (Trends, Ziele,
 * Personen, Parteien), obwohl sie nur die Leiste zeigt. Dieselbe
 * Trennung erlaubt `/council`, den ganzen Reiter erst bei Bedarf zu laden
 * und solange die Leiste schon richtig hinzustellen.
 */
import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useFeature } from "@/lib/features";
import { analysisSections, analysisSub, type AnalysisSection, type AnalysisSub } from "@/lib/analysis-nav";
import { Segmented } from "@/components/ui";
import { ScrollZeile } from "@/components/ui/scroll-zeile";
import { cn } from "@/lib/utils";
import { ANALYSIS_ICONS } from "@/components/analyse-icons";

// Welche Reiter es gibt und wohin sie führen, steht in `lib/analysis-nav.ts`,
// ihre Zeichen in `analyse-icons.ts` — beides speist auch das Untermenü der
// Seitenleiste.
export { analysisSub, type AnalysisSub };

/** Fragen, die zum jeweiligen Unterreiter passen — und die die Beschlüsse
 *  hergeben. Wer hier eine Sackgasse einbaut, zeigt sie Neuen als Erstes.
 *
 *  Jede ist auf Prod gestellt worden, bevor sie hier steht (09.11.2026,
 *  ops-frage-probe). Herausgeflogen sind „Wobei stimmen SPD und CDU
 *  gegeneinander?“ (wer wie gestimmt hat, steht in keinem Protokoll), „Welche
 *  Themen hat der Rat 2026 am häufigsten behandelt?“ (die Suche zählt nicht),
 *  „Was hat der Rat zuletzt beschlossen?“ (das Protokoll der letzten Sitzung
 *  fehlt fast immer noch) und „Welche Klimaziele hat sich der Rat gesetzt?“
 *  (die Antwort widersprach sich). */
export const ANALYSE_FRAGEN: Record<AnalysisSub, readonly string[]> = {
  trends: ["Was hat der Rat 2026 zum Radverkehr beschlossen?", "Was wurde 2026 zum Fliegerhorst entschieden?"],
  parties: ["Welche Anträge hat die SPD 2026 eingebracht?", "Was hat die FDP zuletzt beantragt?"],
  personen: ["Wer hat sich zum Stadionneubau geäußert?", "Was sagte der Oberbürgermeister zur Cäcilienbrücke?"],
  ziele: ["Was steht im Klimaschutzplan 2035?", "Was hat der Rat zur Wärmeplanung beschlossen?"],
};

/* Zwei Reiter mehr, als die Analyse selbst kennt — beide führen auf eine
 * eigene Seite und haben trotzdem keinen eigenen Punkt in der Navigation:
 *
 * „Ideen aus anderen Städten" (`/council/ideen`) — derselbe Name wie
 * Seitentitel, Menü und App (Tims Entscheidung 10/2026; vorher hieß er hier
 * „Andere Städte", in der App „Ideen anderswo"). Die Seite stellt dieselbe
 * Frage wie die Analyse — was tut der Rat? — aus der anderen Richtung: was tun
 * andere Räte, was Oldenburg nicht tut (Tim, 23.09.2026).
 *
 * „Wahlen" (`/wahlen`: Ratswahl, OB-Wahl, Stichwahl, Rückblicke) — der
 * dauerhafte Weg zur Wahl-Auswertung. Tims Entscheidung 03.10.2026: Wahlabend
 * und Tippspiel bleiben, aber nicht mehr prominent; die Auswertung soll
 * trotzdem immer erreichbar sein. Laut (oben auf Heute, auf der Startseite)
 * wird eine Wahl nur noch um ihren Wahltag (`election.prominent`). Am Schalter
 * `wahlabend`, weil die Zielseite daran hängt. */

/** Die Reiterleiste — **nur auf Telefon und iPad** (`desk:hidden`).
 *
 *  Am Schreibtisch stehen dieselben Ziele als Untermenü unter „Analyse" in der
 *  Seitenleiste (seit 11/2026). Beides zugleich wäre dieselbe Navigation
 *  doppelt, 200 px voneinander entfernt (Tim, 22.11.2026: „doppelte Navigation
 *  ist unnötig"). Unterhalb von `desk` gibt es keine Seitenleiste, dort bleibt
 *  die Leiste der einzige Weg.
 *
 *  `className` gilt der Hülle und trägt den Abstand zur Umgebung: Er muss mit
 *  der Leiste verschwinden, sonst bliebe am Schreibtisch eine Lücke stehen. */
export function AnalyseReiter({ aktiv, className }: { aktiv: AnalysisSection; className?: string }) {
  const sp = useSearchParams();
  const router = useRouter();
  const staedte = useFeature("ideen-anderswo");
  // „Pläne“ statt „Ziele“ (Schalter `plaene`): dieselbe Adresse `sub=ziele`,
  // damit alte Links und die App weiter dort landen.
  const plaene = useFeature("plaene");
  const wahlen = useFeature("wahlabend");
  const optionen = analysisSections({ plans: plaene, ideas: staedte, elections: wahlen })
    .map((z) => ({ value: z.key, label: z.label, icon: ANALYSIS_ICONS[z.key] }));
  const wechsel = (s: AnalysisSection) => {
    if (s === aktiv) return;
    if (s === "staedte") { router.push("/council/ideen"); return; }
    if (s === "wahlen") { router.push("/wahlen"); return; }
    // Von der Ideen-Seite zurück: deren Parameter (feld, stand, …) gehören
    // nicht in die Analyse.
    const params = new URLSearchParams(aktiv === "staedte" ? "" : sp.toString());
    params.set("tab", "analysis");
    if (s === "trends") params.delete("sub"); else params.set("sub", s);
    const ziel = `/council?${params.toString()}`;
    if (aktiv === "staedte") router.push(ziel); else router.replace(ziel, { scroll: false });
  };
  // Auf dem Handy läuft die Leiste seitwärts aus dem Bild, und „Ideen aus
  // anderen Städten" steht ganz rechts — ohne das stünde der aktive Reiter außer Sicht
  // (Bild vom 23.09.2026). `nearest` rollt nur waagerecht und nur wenn nötig.
  const huelle = useRef<HTMLDivElement>(null);
  useEffect(() => {
    huelle.current?.querySelector('[aria-pressed="true"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [aktiv, staedte, wahlen]);
  return (
    <div ref={huelle} className={cn("desk:hidden", className)}>
      {/* Die Zeile scrollt auf dem Handy — und zeigt das jetzt mit der
          Ausblend-Maske (Designsprache § 6). Bis 10/2026 stand „€ Finanzen"
          hart angeschnitten am Rand, ohne Hinweis auf weitere Reiter. */}
      <ScrollZeile>
        <Segmented className="w-max" value={aktiv} onChange={wechsel} options={optionen} />
      </ScrollZeile>
    </div>
  );
}
