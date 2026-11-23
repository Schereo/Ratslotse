// Die Fluchttür `/?start=1`: Angemeldete sehen die Startseite trotzdem, und
// der Wunsch gilt für die Sitzung.
//
// Wer das festhält, sind zwei: der Server als Cookie (`lib/landing-redirect.ts`)
// und der Browser in `sessionStorage` — dort liest ihn der Rückfall
// `components/landing-redirect.tsx`, bevor er aufs Dashboard springt.
//
// **Warum der Merker schon beim Einlesen der Seite gesetzt wird.** Bis 11/2026
// setzte ihn allein der Effekt in `LandingRedirect`, also erst nach dem
// Hydrieren. Wer in der Zeit davor weiterging, hatte ihn nicht: Der nächste
// Aufruf von „/" kam vom Server unbehelligt zurück (das Cookie war da), und
// der Rückfall im Browser sprang trotzdem aufs Dashboard. Unter Next 14 war
// die Seite beim `load`-Ereignis fast immer schon hydriert, das Fenster also
// kaum zu treffen. Unter Next 16 kommt `load` früher als das Hydrieren
// (gemessen 22.11.2026: Merker 100 bis 140 ms nach `load`, auf einem
// langsamen Rechner über eine Sekunde) — der Browsertest zur Fluchttür fiel
// in der CI zweimal hintereinander.
//
// Das Skript unten läuft im <head> (app/layout.tsx), bevor irgendein Bündel
// geladen ist. Der Effekt bleibt für den Weg ohne ganzen Seitenaufruf.
//
// Ohne Abhängigkeiten: app/layout.tsx ist eine Server-Komponente.

/** Der Parameter, der die Landing trotz Anmeldung stehen lässt. */
export const LANDING_PARAM = "start";

/** Der Merker in `sessionStorage`. */
export const LANDING_WANTED_KEY = "ratslotse:landing-gewollt";

/** Das Skript für den <head>. Nur auf „/" und nur mit dem Parameter; ein
 *  gesperrter Speicher (privates Fenster) darf die Seite nicht stören. */
export const EARLY_LANDING_SCRIPT =
  `try{if(location.pathname==="/"&&new URLSearchParams(location.search).has(${JSON.stringify(LANDING_PARAM)}))`
  + `sessionStorage.setItem(${JSON.stringify(LANDING_WANTED_KEY)},"1")}catch(e){}`;
