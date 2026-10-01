import { api } from "@/lib/api";

/** Was der Einrichtungs-Assistent angeboten und was jemand angeklickt hat —
 *  als Zähler ohne Personenbezug (`POST /onboarding/chips`).
 *
 *  Anlass (30.09.2026): Neue Konten wählten fast nur Stadtteile, und es gab
 *  keine Zahl dafür, was angezeigt, aber nicht genommen wurde. Die Kennungen
 *  sind eine Positivliste — Namen von Stadtteilen, Straßen oder eigenen Themen
 *  gehen nie raus, und der Server wirft alles weg, was nicht darauf steht. */
export type ChipArt = "district" | "district_suggestion" | "own";

/** Die Kennung eines kuratierten Stadtthemas (`key` aus `council/city_topics.py`). */
export const stadtthemaChip = (key: string): string => `city_topic:${key}`;

/** Fire-and-forget: Ein Zähler, der den Assistenten verzögert oder in einen
 *  Fehler laufen lässt, ist schlimmer als keiner. */
export function meldeChips(gezeigt: readonly string[], gewaehlt: readonly string[] = []): void {
  if (gezeigt.length === 0 && gewaehlt.length === 0) return;
  api.post("/onboarding/chips", { gezeigt, gewaehlt }).catch(() => {});
}

/** Das Bild zu einem Stadtthema. Liegt als Datei im Repo
 *  (`public/themen/<key>.webp`, erzeugt von `scripts/themen_grafiken.py`). */
export const stadtthemaBild = (key: string): string => `/themen/${key}.webp`;
