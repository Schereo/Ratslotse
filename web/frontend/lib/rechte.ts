/**
 * Was das angemeldete Konto darf.
 *
 * Die Regel für die ganze Oberfläche: **gegen ein Recht prüfen, nie gegen
 * einen Rollennamen.** `user.permissions` kommt aus dem Vertrag und wird im
 * Backend aus `kern/roles.py` gerechnet; welche Rolle welches Recht trägt,
 * weiß das Frontend nicht und soll es nicht wissen. Eine neue Rolle wirkt
 * damit ohne Frontend-Release — und in der nativen App ohne Store-Update.
 *
 * Der Gegenentwurf stand bis 09/2026 an sechs Stellen im Code: `user.role ===
 * "admin"`. Jede neue Rolle hätte alle sechs gebraucht, und die vergessene
 * Stelle meldet sich nicht — sie lässt jemanden rein oder sperrt ihn aus.
 *
 * Diese Datei ersetzt `lib/haushalt-frei.ts`: Der Haushalt hing an einem
 * Umgebungs-Gate (`NEXT_PUBLIC_RATSLOTSE_ENV === "dev"`) und hängt jetzt am
 * Recht `budget`. Damit fährt der Bereich mit nach Prod und ist dort für
 * Ratsmitglieder sichtbar, statt für alle zu verschwinden.
 */
import type { User } from "./types";

/** Ein einzelnes Recht — die Aufzählung kommt aus dem Vertrag, nicht von
 *  Hand. Ein hier abgetippter String wäre eine zweite Wahrheit neben dem
 *  Backend und veraltete lautlos. */
export type Recht = NonNullable<User["permissions"]>[number];

/** Alles, was Rechte trägt. Absichtlich nicht `User`: Mehrere Aufrufer halten
 *  nur einen Ausschnitt des Kontos in der Hand (der Einrichtungs-Assistent
 *  etwa), und die sollen dieselbe Prüfung benutzen statt eine eigene. */
type MitRechten = { permissions?: readonly string[] | null };

/**
 * Trägt dieses Konto das Recht?
 *
 * `null`/`undefined` heißt **nein** — und zwar auch, solange `useAuth()` noch
 * lädt. Das ist Absicht: Ein kurz aufblitzender Link, den man gleich darauf
 * nicht mehr anklicken kann, ist schlechter als einer, der eine halbe Sekunde
 * später erscheint. Wer zwischen „lädt noch" und „darf nicht" unterscheiden
 * muss (eine Seite, die sonst 404 zeigt), fragt zusätzlich `loading` ab.
 */
export function hatRecht(user: MitRechten | null | undefined, recht: Recht): boolean {
  return !!user?.permissions?.includes(recht);
}

/** Der Haushalts-Bereich: 20 Seiten, 20 API-Routen, ein Recht. */
export function darfHaushalt(user: MitRechten | null | undefined): boolean {
  return hatRecht(user, "budget");
}

/** Das Admin-Panel. Ersetzt das verstreute `user.role === "admin"`. */
export function darfAdmin(user: MitRechten | null | undefined): boolean {
  return hatRecht(user, "admin");
}
