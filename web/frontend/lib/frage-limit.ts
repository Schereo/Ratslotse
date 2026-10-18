/** Welche Bremse hat eine Frage an „Frag den Rat“ gestoppt?
 *
 *  Zwei Bremsen antworten mit 429: das Fenster (10 Fragen in 10 Minuten,
 *  `app.ratelimit.qa_limiter`) und seit 10/2026 das Tageskontingent
 *  (`council.qa.TAGES_KONTINGENT`). Unterscheiden lassen sie sich nur am
 *  Satz, den der Server schickt: Das Kontingent beginnt mit „Für heute“
 *  (`qa.KONTINGENT_TEXT`). Ein Kopf wie `Retry-After` taugt dafür nicht —
 *  das Web liest die API über Origin-Grenzen, und dort sieht es ihn nicht.
 *
 *  Beim Fenster lohnt „Nochmal versuchen“ in ein paar Minuten, beim
 *  Kontingent erst morgen — deshalb zwei Karten.
 */
export function limitArt(detail: unknown): "tag" | "limit" {
  return typeof detail === "string" && detail.trimStart().startsWith("Für heute") ? "tag" : "limit";
}
