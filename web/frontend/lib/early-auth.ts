// „Wer ist da?" schon während das JS lädt.
//
// Jede Seite fragt als Erstes `/api/auth/me` (lib/auth.tsx) — aber erst nach
// dem Laden, Ausführen und Hydrieren des JS, und bis die Antwort da ist, steht
// in der App nur das Gerüst. Auf dem Telefon liegen damit JS-Download und eine
// volle Netzlaufzeit hintereinander, bevor die Seite überhaupt nach ihren
// Daten fragen kann.
//
// Ein kleines Skript im <head> (app/layout.tsx) startet den Abruf deshalb
// sofort und legt das Versprechen ans Fenster; der erste Abruf von
// `/auth/me` über lib/api.ts nimmt es, statt neu zu fragen.
//
// **Warum kein <link rel="preload" as="fetch">.** Damit fing es an (11/2026),
// und im Browsertest gingen trotzdem ZWEI Anfragen raus: Chromium gibt eine
// vorgeladene Antwort nur bis zum `load`-Ereignis an fetch() weiter, und die
// App fragt oft erst danach — die Vorladung kostete dann eine Anfrage, statt
// eine Netzlaufzeit zu sparen. Das Versprechen hier hält, bis es abgeholt wird.
//
// Ohne Abhängigkeiten: app/layout.tsx ist eine Server-Komponente.

const KEY = "__ratslotseAuthMe";

/** Das Skript für den <head>. `credentials: "include"` wie in lib/api.ts.
 *  Das leere `catch` markiert das Versprechen als behandelt: Scheitert der
 *  Abruf (Funkloch), bevor die App ihn abholt, meldete der Fehlersammler
 *  sonst ein „unbehandeltes" Versprechen. Der Abholer bekommt den Fehler
 *  trotzdem — und behandelt ihn wie jeden anderen Netzfehler. */
export const EARLY_AUTH_SCRIPT =
  `try{var p=fetch("/api/auth/me",{credentials:"include"});p.catch(function(){});window.${KEY}=p}catch(e){}`;

/** Den vorab gestarteten Abruf holen — genau einmal, danach ist er weg.
 *  Ohne Skript (Tests, alte Seite) `null`: dann fragt lib/api.ts selbst. */
export function takeEarlyAuth(): Promise<Response> | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, Promise<Response> | undefined>;
  const p = w[KEY];
  if (!p) return null;
  w[KEY] = undefined;
  return p;
}
