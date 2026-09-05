/** Ersatz für das Paket `server-only`.
 *
 *  Next benutzt es als MARKIERUNG: Ein Modul, das es importiert, darf nicht im
 *  Browser-Bündel landen — der Build bricht sonst ab. Außerhalb von Next gibt
 *  es das Paket nicht, und ein Modul mit dieser Markierung ließe sich gar
 *  nicht laden.
 *
 *  Für die Tests ist die Markierung bedeutungslos: Sie laufen ohnehin auf dem
 *  Server (Node). Diese leere Datei tritt an ihre Stelle; die Markierung
 *  selbst bleibt im Quelltext stehen und wirkt im echten Build weiter.
 */
export {};
