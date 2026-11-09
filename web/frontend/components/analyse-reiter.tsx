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
import { Users, TrendingUp, Target, User, Lightbulb, Vote } from "lucide-react";
import { useFeature } from "@/lib/features";
import { Segmented } from "@/components/ui";
import { ScrollZeile } from "@/components/ui/scroll-zeile";

export type AnalysisSub = "parties" | "trends" | "ziele" | "personen";
// Trends zuerst und als Default: Die Themenfeld-Rückblicke sind der
// zugänglichste Einstieg in die Analyse — Parteien/Personen sind die Vertiefung.
const SUB_TABS: [AnalysisSub, string, typeof Users][] = [
  ["trends", "Trends", TrendingUp],
  ["parties", "Parteien", Users],
  ["personen", "Personen", User],
  // „Finanzen“ stand hier bis 11/2026 — Summen aus Beschlusstexten neben dem
  // echten Haushalt, der dasselbe besser beantwortet (Tim, 09.11.2026).
  ["ziele", "Ziele", Target],
];

/** Der Unterreiter aus `?sub=` — alles Unbekannte ist „Trends". */
export function analysisSub(raw: string | null): AnalysisSub {
  return raw === "parties" || raw === "ziele" || raw === "personen" ? raw : "trends";
}

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

/** Ein Reiter mehr als die Analyse selbst kennt: „Ideen aus anderen Städten"
 *  — derselbe Name wie Seitentitel, Menü und App (Tims Entscheidung 10/2026;
 *  vorher hieß er hier „Andere Städte", in der App „Ideen anderswo"). Er ist
 *  länger als die übrigen Reiter, passt am Schreibtisch aber in die Leiste,
 *  und auf dem Handy läuft die Leiste ohnehin seitwärts. Er führt auf
 *  die Ideen-Seite (`/council/ideen`). Sie stellt dieselbe Frage wie die
 *  Analyse — was tut der Rat? — aus der anderen Richtung: was tun andere Räte,
 *  was Oldenburg nicht tut. Tims Entscheidung 23.09.2026: kein eigener Punkt
 *  in der Navigation, sondern ein Reiter hier. */
type AnalyseReiterWert = AnalysisSub | "staedte" | "wahlen";

/* „Wahlen" ist der dauerhafte Weg zur Wahl-Auswertung (`/wahlen`: Ratswahl,
 * OB-Wahl, Stichwahl, Rückblicke). Tims Entscheidung 03.10.2026: Wahlabend
 * und Tippspiel bleiben, aber nicht mehr prominent — die Auswertung soll
 * trotzdem immer erreichbar sein. Laut (oben auf Heute, auf der Startseite)
 * wird eine Wahl nur noch um ihren Wahltag (`election.prominent`); hier steht
 * sie das ganze Jahr. Gleiche Bauform wie „Andere Städte": kein eigener
 * Navigationspunkt, ein Reiter, der auf die eigene Seite führt. Am Schalter
 * `wahlabend`, weil die Zielseite daran hängt. */

export function AnalyseReiter({ aktiv, className }: { aktiv: AnalyseReiterWert; className?: string }) {
  const sp = useSearchParams();
  const router = useRouter();
  const staedte = useFeature("ideen-anderswo");
  const optionen: { value: AnalyseReiterWert; label: string; icon: typeof Users }[] =
    SUB_TABS.map(([s, lbl, Icon]) => ({ value: s, label: lbl, icon: Icon }));
  const wahlen = useFeature("wahlabend");
  if (staedte) optionen.push({ value: "staedte", label: "Ideen aus anderen Städten", icon: Lightbulb });
  if (wahlen) optionen.push({ value: "wahlen", label: "Wahlen", icon: Vote });
  const wechsel = (s: AnalyseReiterWert) => {
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
    <div ref={huelle}>
      {/* Die Zeile scrollt auf dem Handy — und zeigt das jetzt mit der
          Ausblend-Maske (Designsprache § 6). Bis 10/2026 stand „€ Finanzen"
          hart angeschnitten am Rand, ohne Hinweis auf weitere Reiter. */}
      {className ? (
        <Segmented className={className} value={aktiv} onChange={wechsel} options={optionen} />
      ) : (
        <ScrollZeile>
          <Segmented className="w-max" value={aktiv} onChange={wechsel} options={optionen} />
        </ScrollZeile>
      )}
    </div>
  );
}
