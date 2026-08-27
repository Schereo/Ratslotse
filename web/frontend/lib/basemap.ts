// Kartenhintergrund: CARTO-Rasterkacheln, eine Quelle für alle fünf Karten.
//
// Seit August 2026 verlangt CARTO für diesen Endpunkt einen API-Key. Ohne Key
// kommen die Kacheln zwar weiterhin (HTTP 200, kein Ausfall), tragen aber ein
// „API KEY REQUIRED"-Wasserzeichen quer über jedes einzelne PNG — eingebrannt,
// nicht per Overlay, also nicht wegzustylen.
//
// Der Parameter heißt `key`, NICHT `api_key`: Letzteres wird stillschweigend
// ignoriert und liefert die wasserzeichenbehaftete Kachel mit Status 200
// zurück. Ein Tippfehler fällt hier also nicht als Fehler auf, sondern nur
// daran, dass das Wasserzeichen bleibt.
//
// Der Key ist ein reiner Client-Key: `NEXT_PUBLIC_` heißt, er wird zur
// Build-Zeit ins Browser-Bundle einkompiliert und ist damit öffentlich
// einsehbar. Das ist bei Kartenkeys üblich und der Grund, warum er im
// CARTO-Konto auf unsere Domains beschränkt gehört. Ins Repo gehört er
// trotzdem nicht (öffentliches Repo, Historie ist nicht rückholbar) — er kommt
// aus dem GitHub-Secret `CARTO_API_KEY`, das beide Deploy-Workflows in den
// Build reichen. Lokal: `web/frontend/.env.local` (gitignored).
//
// Fehlt die Variable, bleibt die URL unverändert — die Karte funktioniert
// weiter, nur eben mit Wasserzeichen. Kein harter Fehler, denn eine Karte mit
// Wasserzeichen ist besser als gar keine.
const KEY = process.env.NEXT_PUBLIC_CARTO_API_KEY;

/** Die drei bei uns verwendeten CARTO-Styles und ihr Pfad-Segment. */
const STYLE_PFAD = {
  // Straßennetz, Grünflächen und Wasser deutlich sichtbar; im Dunkelmodus per
  // CSS-Filter eingefärbt (globals.css, .dark .leaflet-tile).
  voyager: "rastertiles/voyager",
  // „Positron"/„Dark Matter" — fast konturlos bzw. fast schwarz, nur noch auf
  // der Einzelort-Karte im Einsatz.
  light: "light_all",
  dark: "dark_all",
} as const;

export type BasemapStyle = keyof typeof STYLE_PFAD;

/**
 * Leaflet-Kachel-URL für einen CARTO-Style, mit API-Key sofern gesetzt.
 *
 * `{s}`/`{z}`/`{x}`/`{y}`/`{r}` bleiben als Leaflet-Platzhalter stehen; `{r}`
 * wird auf Retina-Displays zu „@2x".
 */
export function basemapUrl(style: BasemapStyle = "voyager"): string {
  const url = `https://{s}.basemaps.cartocdn.com/${STYLE_PFAD[style]}/{z}/{x}/{y}{r}.png`;
  return KEY ? `${url}?key=${encodeURIComponent(KEY)}` : url;
}
