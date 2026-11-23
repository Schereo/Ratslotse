/**
 * Die vier Etappen des Haushalts als Untermenü der Seitenleiste.
 *
 * Die Etappen und nicht die zwölf Schritte: Zwölf Zeilen wären rund 480 px,
 * und „Persönlich" rutschte auf einem Notebook aus dem Bild. Die Schritte
 * INNERHALB einer Etappe zeigt weiter der Schritt-Pfad im Seitenkopf
 * (`schritt-pfad.tsx`) — die Seitenleiste sagt, in welchem Teil des Weges man
 * steht, der Pfad, an welcher Stelle darin.
 *
 * **Abgeleitet, nicht abgeschrieben:** `wegweiser.tsx` ist die einzige Quelle
 * der Reihenfolge (s. dort, `tests/test_haushalt_schritte.py`).
 *
 * **Eigene Datei, weil die Navigation sie NACHLÄDT** (`components/nav.tsx`).
 * Ein direkter Import zöge den ganzen Wegweiser — Schlangenpfad, Lesestand,
 * siebzehn Symbole — in die Hülle jeder Seite, für einen Bereich, den nur
 * Konten mit dem Recht `budget` überhaupt sehen.
 */
import type { LucideIcon } from "lucide-react";
import { ETAPPEN, SCHRITTE } from "@/components/haushalt/wegweiser";

export type BudgetStage = {
  key: string;
  label: string;
  /** Der erste Schritt der Etappe — dorthin führt die Zeile. */
  href: string;
  /** Das Zeichen dieses ersten Schritts: Die Zeile trägt das Zeichen der
   *  Seite, auf der man landet — keine zweite Zuordnung, die neben den
   *  Schritten gepflegt werden müsste. */
  icon: LucideIcon;
  /** Alle Schritt-Seiten der Etappe: Auf jeder davon ist sie der Standort. */
  steps: string[];
};

export const BUDGET_STAGES: BudgetStage[] = ETAPPEN.map((stage) => {
  const steps = SCHRITTE.filter((s) => s.nr >= stage.von && s.nr <= stage.bis);
  const first = steps[0];
  return { key: first.href, label: stage.kicker, href: first.href, icon: first.zeichen, steps: steps.map((s) => s.href) };
});
