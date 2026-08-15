import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  // Zeitanteil abschneiden: Kommt hier ein voller Zeitstempel an
  // („2026-07-24T09:21:18“), ergäbe die Zerlegung an „-“ sonst „24T09:21:18.07.2026“.
  const parts = iso?.split("T")[0]?.split("-");
  if (parts?.length === 3) return `${parts[2]}.${parts[1]}.${parts[0]}`;
  return iso || "";
}

/** „24.07.2026, 09:21“ — für Zeitstempel, bei denen die Uhrzeit zählt
 *  (Feedback-Eingang). Ohne Zeitanteil identisch zu {@link formatDate}. */
export function formatDateTime(iso: string): string {
  const [datum, zeit = ""] = (iso || "").split("T");
  const hhmm = zeit.slice(0, 5);
  return hhmm ? `${formatDate(datum)}, ${hhmm}` : formatDate(datum);
}

/** „heute“ / „morgen“ / „gestern“ — oder null, wenn der Tag weiter weg ist.
 *
 *  Tims Wunsch 12.08.: Ein Termin am nächsten Tag soll das auch sagen, statt
 *  „Do., 13.08.“ zu zeigen und die Rechnung dem Kopf zu überlassen.
 *  `heute` kommt als Parameter, weil der statische Export sonst das
 *  Build-Datum einbacken würde (siehe `useHeute`).
 */
/** Wochentag kurz („Mi.") — im Sitzungstab steht sonst nur „AUG 13", und man
 *  rechnet selbst nach, ob das ein Werktag oder ein Wochenende ist. */
export function wochentagKurz(iso: string): string {
  const tag = (iso || "").split("T")[0];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(tag)) return "";
  return new Date(tag + "T12:00:00").toLocaleDateString("de-DE", { weekday: "short" });
}

export function relativerTag(iso: string, heute: Date | null): string | null {
  if (!heute) return null;
  const tag = (iso || "").split("T")[0];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(tag)) return null;
  const lokal = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const plus = (n: number) => {
    const d = new Date(heute);
    d.setDate(d.getDate() + n);
    return lokal(d);
  };
  if (tag === lokal(heute)) return "heute";
  if (tag === plus(1)) return "morgen";
  if (tag === plus(-1)) return "gestern";
  return null;
}

/** Pfad ohne Schluss-Schrägstrich — die EINE Stelle, an der die Eigenheit des
 *  App-Exports aufgefangen wird.
 *
 *  `next.config.mjs` setzt für den statischen Export `trailingSlash: true`:
 *  In der iOS/Android-App heißt der Pfad also `/council/`, im Web `/council`.
 *  Jeder exakte Vergleich (`pathname === "/council"`) war damit in der App
 *  blind — der Sitzungen-Tab leuchtete nie (Tims Befund 12.08.), und nach dem
 *  Split hätten dieselben Vergleiche das Ratsgespräch daran gehindert, eine
 *  vorbefüllte Frage oder einen geteilten Snapshot zu übernehmen.
 */
export function pfad(pathname: string | null | undefined): string {
  const p = String(pathname ?? "");
  return p.length > 1 ? p.replace(/\/+$/, "") || "/" : p || "/";
}
