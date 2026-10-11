"use client";

import { ErrorState } from "@/components/ui";
import { ApiError, FEHLER_OFFLINE } from "@/lib/api";

/** Der Fehlerzustand für eine Seite, deren Hauptabruf nicht ankam.
 *
 *  Gegenstück zu `notFound()`: Das gilt nur für ein echtes 404. Alles andere
 *  — Funkloch, Zeitüberschreitung, ein 500er, ein Deploy — ist „kam nicht an",
 *  und dafür braucht es einen Weg hinaus statt einer Sackgasse. */
export function AbrufFehler({ error, onRetry, was = "Diese Seite" }: {
  error: unknown;
  onRetry?: () => void;
  /** Was nicht geladen werden konnte, als Satzanfang: „Dieser Beschluss". */
  was?: string;
}) {
  // `ApiError` bringt schon einen lesbaren Satz mit (lib/api.ts übersetzt
  // Funkloch, Zeitüberschreitung und Deploy). Eigene Fehlerklassen mit
  // `status` (das Tippspiel ruft ohne den Wrapper ab) bekommen einen.
  const roh = (error as { status?: unknown } | null)?.status;
  const hint = error instanceof ApiError ? error.message
    : typeof roh === "number" && roh >= 500
      ? "Auf unserer Seite ist etwas schiefgegangen. Wir sehen das und kümmern uns darum."
      : FEHLER_OFFLINE;
  return (
    <div className="py-6">
      <ErrorState title={`${was} konnte gerade nicht geladen werden`} hint={hint} onRetry={onRetry} />
    </div>
  );
}
