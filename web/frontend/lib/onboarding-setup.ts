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
