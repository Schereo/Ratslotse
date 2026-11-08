// Maße der festen Leisten der App-Hülle — ohne jede Abhängigkeit.
//
// Sie standen bis 11/2026 in components/nav.tsx. Wer nur die Zahl brauchte,
// holte damit die ganze Navigation samt Lotti-Fenster, Befehlspalette und
// Viertel-Bausteinen ins Bündel: Die öffentliche Teilen-Seite /g lud über
// components/grafik/ablesen.tsx gut 110 KB (gzip) JS mehr, als sie brauchte.
// nav.tsx reicht die Werte weiter; neue Stellen importieren von hier.

/** Höhe der Tab-Leiste (inkl. Sicherheitszone) — die EINE Quelle dafür.
 *
 *  Bis 16.08. war die Leiste inhaltsgetrieben hoch, und alles, was auf ihr
 *  aufsitzt, riet ihre Höhe mit einer eigenen Zahl: der fixierte Composer im
 *  Ratsgespräch mit `4rem`, das „Mehr"-Sheet und der Platzhalter in `main` mit
 *  `4.75rem`. Nachgemessen war sie aber je Breakpoint verschieden hoch — 63 px
 *  auf dem Telefon, 61 px ab `md` (dort `py-1` statt `py-2`, dafür größere
 *  Symbole). Zwischen Composer-Unterkante und Leisten-Oberkante blieb dadurch
 *  ein Streifen offen, durch den der Antworttext scrollte (Tims iPad-Befund
 *  16.08.). Zwei Zahlen an zwei Orten laufen immer wieder auseinander; deshalb
 *  ERZWINGT die Leiste diese Höhe, und wer an ihr andockt, importiert
 *  denselben Ausdruck, statt ihn nachzubauen.
 *
 *  Wer hier etwas ändert, ändert damit auch die Andockkante des Composers —
 *  das ist der Sinn. Nur `main` in app/(app)/layout.tsx rechnet noch mit einer
 *  eigenen Zahl (4.75rem = diese Höhe + Luft); das ist ein Platzhalter im
 *  Fluss, der ein paar Pixel Toleranz verträgt. */
const TABLEISTE_INHALT = "4rem"; // die Leiste selbst, ohne Sicherheitszone
export const TABLEISTE_HOEHE = `calc(env(safe-area-inset-bottom) + ${TABLEISTE_INHALT})`;

/** Höhe der mobilen Kopfleiste (inkl. Sicherheitszone) — dieselbe Rolle für
 *  oben: `pt-0.75rem` + Inhalt `h-9` + `pb-3` + 1 px Rahmen = 3.8125rem. Wer
 *  etwas unter dem Kopf festpinnt (die Belege-Spalte auf dem iPad), nimmt das
 *  hier statt einer geschätzten Zahl. */
export const KOPFLEISTE_HOEHE = "calc(env(safe-area-inset-top) + 3.8125rem)";
