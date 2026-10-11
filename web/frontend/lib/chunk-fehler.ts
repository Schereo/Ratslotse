/** Nach einem Deploy: alte Seite offen, ihre Programmteile gibt es nicht mehr.
 *
 *  Der nächste nachgeladene Teil (Karte, Lotti, eine andere Seite) scheitert
 *  dann mit einem `ChunkLoadError`, und die Fehlerseite fängt ihn. Ihr
 *  „Erneut versuchen" (`reset`) rendert aber nur neu — der Teil fehlt
 *  weiterhin, man kam nicht heraus. Was hilft, ist ein echtes Neuladen; das
 *  holt die neue Fassung. Einmal, nicht in Schleife: Scheitert es danach
 *  wieder, ist es kein Deploy-Rest, und die Fehlerseite bleibt stehen. */

const SCHLUESSEL = "ratslotse.chunk-neu-geladen";
const SPERRE_MS = 60_000;

export function istChunkFehler(e: unknown): boolean {
  if (!e || typeof e !== "object") return false;
  const name = (e as { name?: unknown }).name;
  const text = String((e as { message?: unknown }).message ?? "");
  return name === "ChunkLoadError"
    || /Loading (CSS )?chunk [\w-]+ failed/i.test(text)
    || /Failed to fetch dynamically imported module/i.test(text)
    || /error loading dynamically imported module/i.test(text);
}

/** Lädt einmal neu, wenn es ein Deploy-Rest ist und das letzte Neuladen
 *  länger als eine Minute her ist. Gibt zurück, ob neu geladen wird. */
export function chunkFehlerHeilen(
  e: unknown,
  speicher: Pick<Storage, "getItem" | "setItem"> | null = typeof window !== "undefined" ? window.sessionStorage : null,
  neuLaden: () => void = () => window.location.reload(),
  jetzt: number = Date.now(),
): boolean {
  if (!istChunkFehler(e) || !speicher) return false;
  try {
    const zuletzt = Number(speicher.getItem(SCHLUESSEL) ?? 0);
    if (jetzt - zuletzt < SPERRE_MS) return false;
    speicher.setItem(SCHLUESSEL, String(jetzt));
  } catch {
    return false; // ohne Speicher keine Schleifensperre — dann lieber gar nicht
  }
  neuLaden();
  return true;
}
