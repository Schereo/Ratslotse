import { ExternalLink } from "lucide-react";

/** Kurze, saubere Suchanfrage aus einem (oft sehr langen, bürokratischen)
 *  Beschlusstitel. Lange Titel mit Klammer-Zusätzen, Daten und „- Bericht"-
 *  Anhängseln bringen die NWZ-Suche clientseitig zum Hängen (Dauer-Ladeschleife);
 *  darum reduzieren wir auf die ersten Schlagworte. */
export function nwzQuery(title: string): string {
  // Hinweis: JS-\b ist ASCII-only und greift nach „ß"/„§" nicht — darum enden
  // die Schwanz-Muster auf Whitespace statt auf \b.
  const cleaned = (title || "")
    .replace(/\([^)]*\)/g, " ")                    // Klammer-Zusätze, z. B. (Stadtplanung)
    .replace(/\s[-–—]\s.*$/, " ")                  // alles ab „ - Bericht/Antrag/…"
    .replace(/\s(?:zum stichtag|gemäß|nach §|für den zeitraum)\s.*$/i, " ")  // Datum/Paragraph/Zeitraum
    .replace(/\svom\s+\d.*$/i, " ")                // „vom 5. Mai 2025" (nur vor Datum)
    .replace(/["«»„""'']/g, " ")                    // Anführungszeichen
    .replace(/\s+/g, " ")
    .trim();
  const words = cleaned.split(" ").filter(Boolean).slice(0, 6).join(" ");
  return words.length > 60 ? words.slice(0, 60).trim() : words;
}

/** NWZonline-Suche zu einem Beschluss — der e-Paper-Feed hat keine kanonische
 *  Artikel-URL, deshalb die Suche. Schrägstrich Pflicht: /suche/?query=… füllt
 *  das Suchfeld, /suche?query=… lässt es leer. Query wird gekürzt (siehe oben). */
export function nwzSearchUrl(title: string): string {
  return `https://www.nwzonline.de/suche/?query=${encodeURIComponent(nwzQuery(title))}`;
}

/** A small, neutral "read at NWZonline" link — no mention of access tiers. */
export function NwzReadHint({ title }: { title: string }) {
  return (
    <a
      href={nwzSearchUrl(title)}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
    >
      <ExternalLink className="h-3.5 w-3.5" /> Bei NWZonline lesen
    </a>
  );
}
