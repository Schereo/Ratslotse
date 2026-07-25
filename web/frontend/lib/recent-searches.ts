// Zuletzt gesuchte Begriffe — rein client-seitig (localStorage, kein Backend),
// nach dem Muster von lib/recent.ts. Design 28a/R6: Die Befehlspalette merkt
// sich Suchen längst, das große Suchfeld auf der Beschluss-Seite nicht — man
// tippt „Fahrradstraße Haarenfeld" jedes Mal neu.

const KEY = "ratslotse:recent-searches";
const MAX = 5;
const MIN_LEN = 3;

/** Merkt einen Suchbegriff. Präfixe des neuen Begriffs fliegen raus: Wer
 *  „radwege" tippt, erzeugt beim Debounce unterwegs „rad" und „radweg" — die
 *  Liste soll das Ziel enthalten, nicht den Weg dorthin. */
export function pushRecentSearch(query: string): void {
  const q = query.trim();
  if (q.length < MIN_LEN) return;
  try {
    const lower = q.toLowerCase();
    const next = [
      q,
      ...getRecentSearches().filter((r) => {
        const rl = r.toLowerCase();
        return rl !== lower && !lower.startsWith(rl);
      }),
    ].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* Storage voll/gesperrt — Feature ist optional */
  }
}

export function getRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function clearRecentSearches(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* egal */
  }
}
