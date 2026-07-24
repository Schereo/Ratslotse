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
