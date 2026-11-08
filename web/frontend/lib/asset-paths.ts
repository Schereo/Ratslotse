/** Versionierte Adressen für die Bündel unter `public/lotti` und `public/geo`.
 *
 * Next liefert Dateien aus `public/` mit `Cache-Control: public, max-age=0`
 * aus. Beim Folgebesuch fragt deshalb jede Seite jede Lotti-Datei einmal
 * nach (304), bevor die Figur steht — gemessen vier bis sechs Nachfragen je
 * Seite. Eine Lebensdauer einfach dazuzuschreiben ginge schief, weil die
 * Dateien zusammengehören: Kommt nach einer Übernahme aus dem Lotti-Studio ein
 * neues `lotti.json` zu einem noch zwischengespeicherten alten Blatt, rechnet
 * der Abspieler mit dem neuen Raster im alten Bild und zeigt halbe Nachbarn.
 * Bei den Geodaten liest der Code Feldnamen, die mit einer Datei wechseln
 * können.
 *
 * Deshalb trägt die ADRESSE den Inhalt: `next.config.mjs` bildet beim Start
 * (also beim Bauen) einen Fingerabdruck über alle Dateien des Ordners. Unter
 * `/lotti/v/<abdruck>/…` liefert ein Rewrite dieselbe Datei wie unter
 * `/lotti/…`, nur mit einem Jahr Lebensdauer. Ändert sich irgendeine Datei des
 * Bündels, ändert sich die Adresse ALLER — ein neues Verzeichnis trifft nie
 * auf ein altes Blatt. Ohne Fingerabdruck (Tests, fehlender Ordner) bleibt es
 * bei der alten, unversionierten Adresse.
 *
 * Die unversionierten Adressen funktionieren weiter (E-Mails, README,
 * Standbilder), nur eben ohne Lebensdauer.
 */
const LOTTI_VERSION = process.env.LOTTI_BUNDLE_VERSION;
const GEO_VERSION = process.env.GEO_BUNDLE_VERSION;

/** Wurzel des Lotti-Bündels, mit Schrägstrich am Ende. */
export const LOTTI_BASE = LOTTI_VERSION ? `/lotti/v/${LOTTI_VERSION}/` : "/lotti/";

/** Adresse einer Datei aus `public/geo/`. */
export function geoUrl(file: string): string {
  return GEO_VERSION ? `/geo/v/${GEO_VERSION}/${file}` : `/geo/${file}`;
}
