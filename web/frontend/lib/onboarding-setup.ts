import { api } from "@/lib/api";

/** Server-Stand des Einrichtungs-Assistenten. `pending` beantwortet „ist er
 *  dran?" — die Regel steht im Backend (`Store.get_setup`), damit Web und App
 *  dieselbe Antwort bekommen und das Frontend nicht erst Themen und Abos
 *  zählen muss. */
export type SetupStand = {
  step: number;
  started_at: string | null;
  done_at: string | null;
  pending: boolean;
};

/** Schlüssel und Abruf stehen hier statt im Assistenten selbst: Die
 *  Bestätigungsseite und die „Bitte bestätige deine E-Mail"-Hülle legen den
 *  Stand in den Cache, BEVOR sie weiterschicken — sonst stünde nach der
 *  Bestätigung erst „Heute" und der Assistent schöbe sich eine Antwort später
 *  darüber. Beide sollen dafür nicht die ganze Assistenten-Datei laden. */
export const SETUP_QUERY_KEY = ["onboarding-setup"] as const;
export const holeSetupStand = () => api.get<SetupStand>("/onboarding/setup");

/** Der höchste Schritt, den der Server annimmt (`SetupUpdate.step`, `le=4`):
 *  1 Gremien, 2 Stadtteil, 3 Themen, 4 Mitteilungen. */
export const LETZTER_SETUP_SCHRITT = 4;

/** Welcher Schritt an den Server geht. Der Assistent kennt einen Schritt 5 —
 *  das Auffangnetz „noch kein Thema, kein Gremium" —, der kein Schritt im
 *  Pfad ist. Bis 10/2026 ging er trotzdem als 5 raus und kam als 422 zurück
 *  (verschluckt, weil die Meldung fire-and-forget ist). Wer dort steht, hat
 *  den Pfad hinter sich; gemeldet wird also der letzte echte Schritt. */
export function gemeldeterSetupSchritt(step: number): number {
  return Math.max(0, Math.min(LETZTER_SETUP_SCHRITT, Math.trunc(step)));
}
