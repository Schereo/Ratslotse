/**
 * Kleine Logik der Seite „Ideen aus anderen Städten" — rein, ohne React,
 * damit sie prüfbar ist (`ideen.test.ts`).
 */
import { ApiError } from "./api";
import type { ApiAntwort } from "./vertrag";

export type Datenstand = ApiAntwort<"/council/cities/ideas/fields">["data_status"];

function datum(iso: string): string {
  const [j, m, t] = iso.slice(0, 10).split("-");
  return `${t}.${m}.${j}`;
}

/** „A, B und C" — es ist ein Satz, keine Liste. */
export function aufzaehlung(namen: string[]): string {
  if (namen.length < 2) return namen.join("");
  return `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
}

/**
 * „Stand: 10.09.2026" und, wo nötig, der Satz zu Städten mit altem Bestand.
 *
 * Kein Versprechen über den nächsten Abgleich: Wann er läuft, weiß diese
 * Seite nicht — sie sagt nur, wie alt das ist, was sie zeigt. Ohne Abgleich
 * gibt es auch keinen Stand (kein erfundenes Datum).
 */
export function standZeilen(stand: Datenstand | undefined | null): { stand: string | null; luecke: string | null } {
  if (!stand?.as_of) return { stand: null, luecke: null };
  const hinten = stand.lagging ?? [];
  let luecke: string | null = null;
  if (hinten.length === 1) {
    const h = hinten[0];
    luecke = `Aus ${h.city} liegen Vorlagen nur bis ${datum(h.latest_paper)} vor.`;
  } else if (hinten.length > 1) {
    luecke = `Aus ${aufzaehlung(hinten.map((h) => `${h.city} (bis ${datum(h.latest_paper)})`))} `
      + "liegen nur ältere Vorlagen vor.";
  }
  return { stand: `Stand: ${datum(stand.as_of)}`, luecke };
}

/**
 * Warum „Stimmt das?" nicht geklappt hat — in einem Satz, der sagt, was zu tun ist.
 *
 * Bis 10/2026 stand bei JEDEM Fehlschlag „Dafür braucht es ein Konto" —
 * auch bei einem angemeldeten Konto, dessen Adresse noch nicht bestätigt ist
 * (403), oder wenn die Bremse griff (429).
 */
export function rueckmeldungsFehler(fehler: unknown): string {
  const status = fehler instanceof ApiError ? fehler.status : 0;
  if (status === 401) return "Dafür braucht es ein Konto.";
  if (status === 403) return "Dafür muss dein Konto bestätigt sein.";
  if (status === 429) return "Gerade zu viele Rückmeldungen — gleich noch einmal.";
  return "Das hat nicht geklappt — bitte noch einmal.";
}

/** Gibt es das nicht, oder kam die Antwort nicht an? Wohnt in `lib/api.ts`. */
export { istNichtGefunden } from "./api";
