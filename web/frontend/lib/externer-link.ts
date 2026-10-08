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
  // Was Server und Browser verschieden lesen, fliegt raus: Python hält `\`
  // für ein Zeichen im Host, der Browser für `/`. Aus
  // `https://evil.example\@www.oldenburg.de/` las die Prüfung beim Anlegen
  // den Host www.oldenburg.de, der Browser ging zu evil.example (10/2026,
  // F23). Ältere Snapshots tragen solche Werte womöglich schon.
  if (/[\u0000-\u0020\u007F\\]/.test(url)) return undefined;
  try {
    const u = new URL(url);
    if (u.protocol !== "https:" || u.username || u.password) return undefined;
    // Die aufgelöste Form ausliefern, nicht die Eingabe: Was im href steht,
    // ist dann genau das, was geprüft wurde.
    return u.href;
  } catch {
    return undefined;
  }
}
