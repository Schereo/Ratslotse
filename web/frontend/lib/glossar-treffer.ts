/**
 * Welche Fachwörter stehen in diesem Text? — die Erkennung, einmal.
 *
 * **Warum ein eigenes Modul.** Die Regel wohnte in
 * `components/glossary-text.tsx` und war dort an das Zeichnen gebunden: Wer
 * nur wissen will, WELCHE Begriffe in einem Text stecken (der
 * Anschlussfragen-Chip „Was heißt …?" in Lottis Fenster), musste entweder
 * eine React-Komponente aufrufen oder die Regex ein zweites Mal schreiben.
 * Zwei Fassungen liefen unweigerlich auseinander — und dann unterstriche die
 * Antwort ein Wort, das der Chip nicht anbietet, oder umgekehrt.
 *
 * Die Begriffe und ihre Erklärungen stehen in `lib/glossary.ts`; das ist eine
 * erzeugte Datei (Quelle `kern/glossar.py`). Hier steht nur, wie man sie in
 * einem Fließtext findet.
 */
import { GLOSSARY } from "@/lib/glossary";

/** Begriffe längster zuerst, damit „Doppelhaushalt" vor „Haushalt" greift. */
export const BEGRIFF_KEYS = Object.keys(GLOSSARY).sort((a, b) => b.length - a.length);

/** Kleinschreibung → Grundform, wie sie in `GLOSSARY` steht. */
export const BEGRIFF_KANON = new Map(BEGRIFF_KEYS.map((k) => [k.toLowerCase(), k]));

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Wortanfang (nicht von einem Buchstaben vorangestellt) + Begriff +
 *  Buchstaben-Suffix (`\p{L}` mit u-Flag fängt Umlaute; deckt Beugungen wie
 *  -s/-en ab). Dieselbe Regel wie `kern/glossar.py::_TREFFER`. */
export const BEGRIFF_RE = new RegExp(
  `(?<!\\p{L})(${BEGRIFF_KEYS.map(esc).join("|")})(\\p{L}*)`, "giu");

/**
 * Die Grundformen der Fachwörter in einem Text — in Reihenfolge des
 * Auftauchens, jede höchstens einmal.
 *
 * Spiegelt `kern/glossar.py::finde` (das Backend braucht dieselbe Liste für
 * den Prompt). Der Deckel ist kein Geschmack: Eine Antwort über den Haushalt
 * trifft leicht acht Begriffe, und ein Aufrufer, der nur den ersten braucht,
 * soll nicht die ganze Antwort durchrechnen.
 */
export function begriffeIn(text: string, max = 5): string[] {
  const aus: string[] = [];
  const gesehen = new Set<string>();
  // `matchAll` arbeitet auf einer eigenen Kopie der Regex — der gemeinsame
  // Zustand (`lastIndex`) einer globalen Regex kann hier also nicht durch-
  // schlagen, auch wenn `BEGRIFF_RE` an mehreren Stellen benutzt wird.
  for (const m of (text ?? "").matchAll(BEGRIFF_RE)) {
    const key = BEGRIFF_KANON.get(m[1].toLowerCase());
    if (!key || gesehen.has(key)) continue;
    gesehen.add(key);
    aus.push(key);
    if (aus.length >= max) break;
  }
  return aus;
}
