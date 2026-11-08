import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";

/**
 * Die anstehenden Sitzungen auf „Heute" — EINE Abfrage für die Live-Karte
 * (`LiveBanner`) und die Karte „Nächste Sitzung".
 *
 * Bis 11/2026 holten beide dieselbe Liste getrennt: die Live-Karte 6 Sitzungen
 * sofort, die Nächste-Sitzung-Karte 12, aber erst, nachdem die Wochenvorschau
 * `found: false` gemeldet hatte — eine zweite Wasserfall-Stufe für Daten, die
 * längst im Cache lagen. Jetzt liegt die Liste unter einem Schlüssel, und die
 * Karte findet sie beim Einhängen schon vor.
 *
 * 12 ist die Obermenge: Die Live-Karte braucht den längsten Sitzungstag (ein
 * Ratstag bringt drei Gremien nacheinander, s. `lib/live`), die Nächste-
 * Sitzung-Karte alle Gremien des nächsten Sitzungstags. Die Reihenfolge ist
 * dieselbe (Datum, Uhrzeit), die ersten sechs sind also die sechs von früher.
 */
export const UPCOMING_SESSIONS_KEY = ["upcoming-sessions"] as const;

/** Der Typ-Parameter erlaubt der Live-Karte ihre eigene, engere Sicht auf
 *  dieselbe Antwort; zur Laufzeit ist es derselbe Aufruf. */
export function fetchUpcomingSessions<T = ApiAntwort<"/council/sessions">>() {
  return api.get<T>("/council/sessions?scope=upcoming&limit=12");
}
