/**
 * Die Zeichen der Analyse-Unterseiten — EINE Zuordnung für beide Bauformen.
 *
 * Die Reiterleiste (Telefon, iPad) und das Untermenü der Seitenleiste
 * (Schreibtisch) zeigen dieselben Ziele; trügen sie verschiedene Zeichen,
 * sähe derselbe Ort auf zwei Geräten nach zwei Orten aus. Welche Ziele es
 * gibt und wohin sie führen, steht in `lib/analysis-nav.ts` — dort bewusst
 * ohne Zeichen, damit die Logik ohne React unter Test steht.
 */
import { Lightbulb, Target, TrendingUp, User, Users, Vote, type LucideIcon } from "lucide-react";
import type { AnalysisSection } from "@/lib/analysis-nav";

export const ANALYSIS_ICONS: Record<AnalysisSection, LucideIcon> = {
  trends: TrendingUp,
  parties: Users,
  personen: User,
  ziele: Target,
  staedte: Lightbulb,
  wahlen: Vote,
};
