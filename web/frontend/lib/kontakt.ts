/**
 * Die Kontaktadresse des Betreibers — an einer Stelle.
 *
 * Sie stand bis 09/2026 an sechs Stellen wörtlich im Code: Impressum,
 * Datenschutz, Barrierefreiheit, Hilfe und der Fehlertext des
 * Kontaktformulars. Das fiel nicht auf, solange sie sich nicht ändert — und
 * genau das ist die Falle: Wer sie einmal ändert, ändert sie an fünf Stellen
 * und übersieht die sechste, und dann steht auf einer Rechtsseite eine
 * Adresse, die niemand mehr liest.
 *
 * Die iOS-App führt ihre eigene Kopie (`RatslotseKontakt` in `AuthViews.swift`)
 * — sie kann aus TypeScript nichts importieren. Wer hier ändert, ändert dort
 * mit; `tests/test_kontaktadresse.py` hält die beiden zusammen.
 */
export const KONTAKT_EMAIL = "ratslotse@timsigl.de";

/** `mailto:`-Adresse für ein `href`. */
export const KONTAKT_MAILTO = `mailto:${KONTAKT_EMAIL}`;
