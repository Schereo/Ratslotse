"use client";

/**
 * Feature-Schalter im Frontend.
 *
 * Die Wahrheit steht im Backend (`kern/features.py`) und kommt über
 * `/api/app-config` — denselben Endpunkt, den die native App vor allem
 * anderen abfragt. **Bewusst nicht über `NEXT_PUBLIC_…`**: Das wird zur
 * Bauzeit einkompiliert, ein Umlegen bräuchte also einen Neubau und einen
 * Deploy — genau das, was der Schalter ersparen soll.
 *
 * Ein Schalter sagt, ob etwas **schon so weit** ist. Wer regeln will, **wer**
 * etwas sehen darf, nimmt ein Recht (`lib/rechte.ts`); das setzt das Backend
 * durch. Ein Schalter ist keine Sperre.
 *
 * ```tsx
 * const labor = useFeature("haushalt-labor");
 * if (!labor) return null;
 * ```
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type AppConfig = { min_build: number; note: string | null; features?: string[] };

/**
 * Der reine Kern — ohne React, damit er prüfbar ist.
 *
 * `undefined` als Konfiguration heißt „noch nicht geladen" und ergibt
 * **aus**. Das ist Absicht und dieselbe Regel wie bei den Rechten: Eine
 * Fläche, die kurz aufblitzt und dann verschwindet, ist schlechter als eine,
 * die eine halbe Sekunde später erscheint.
 */
export function featureAktiv(config: AppConfig | undefined | null, name: string): boolean {
  return !!config?.features?.includes(name);
}

/** Die App-Konfiguration. Öffentlich, also ohne Konto abrufbar; einmal je
 *  Sitzung reicht — Schalter wechseln nicht im Minutentakt. */
export function useAppConfig() {
  return useQuery({
    queryKey: ["app-config"],
    queryFn: () => api.get<AppConfig>("/app-config"),
    staleTime: 5 * 60 * 1000,
    // Ein Fehler hier darf keine Seite umbringen: Ohne Antwort ist jeder
    // Schalter aus, und das ist der sichere Zustand.
    retry: 1,
  });
}

/** Ist dieser Schalter an? */
export function useFeature(name: string): boolean {
  const { data } = useAppConfig();
  return featureAktiv(data, name);
}
