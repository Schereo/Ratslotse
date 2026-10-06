/** Ein Link nach draußen — nur, wenn er wirklich einer ist.
 *
 *  Geteilte Antworten (`/g`) sind öffentlich, und ihr Inhalt kam bis 10/2026
 *  ungeprüft vom Client: Presse- und Anlagen-Links konnten auf beliebige
 *  Seiten zeigen oder `javascript:`-URLs sein (React 18 rendert die nur mit
 *  einer Warnung in der Entwicklung). Das Backend prüft die Hosts seither
 *  beim Anlegen; diese Prüfung ist die zweite Linie für schon gespeicherte
 *  Snapshots und alles, was künftig ungeprüft hereinkommt. */
export function nurHttps(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url).protocol === "https:" ? url : undefined;
  } catch {
    return undefined;
  }
}
