/**
 * „Neu bei Ratslotse" — was Karte und Spieler rechnen, ohne zu zeichnen.
 *
 * Die Karte zeigt seit 3.0.0 je Highlight eine **Video-Kachel** und öffnet
 * auf Tipp einen **Story-Spieler** (Tims Befund 07.10.2026: „Die Karte fühlt
 * sich langweilig an; ich weiß nicht, ob ich Bock habe, da unten
 * durchzuklicken — mehr Bilder, mehr Anreiz."). Was dabei zu entscheiden
 * ist — welche Farbe, welche Dauer, was schon angesehen ist —, steht hier und
 * ist unter Test; die Komponenten stellen nur dar.
 *
 * Was der SERVER entscheidet, wird hier nicht nachgebaut: Wer die Karte sieht,
 * welches Bild die Kachel trägt (`cover`), welche Farbe und welcher Knopf-Text
 * ohne eigene Angabe gelten — das kommt fertig aus `GET /news`
 * (`kern/releases.py`), damit die App dieselbe Kachel zeigt.
 */
import type { ApiAntwort } from "@/lib/vertrag";

export type NewsState = ApiAntwort<"/news">;
export type Release = NewsState["releases"][number];
export type Highlight = Release["highlights"][number];

/** Die Farben der Video-Kacheln — die Werte stehen in DESIGNSPRACHE.md
 *  („Neuigkeiten-Kacheln") und in der App (`ReleaseNewsCard.swift`).
 *
 *  **Feste Werte statt Theme-Token.** Auf der Kachel steht weiße Schrift; im
 *  Dunkelmodus werden `--primary` und `--signal` HELL (Text darauf dunkel),
 *  Weiß fiele dort auf 2,5 : 1. Die Kachel ist ein Titelbild — ein Bild
 *  wechselt mit dem Theme nicht die Farbe, so wenig wie die Clips selbst
 *  (immer hell, `kern/releases.py`). Alle drei tragen Weiß mit mindestens
 *  4,5 : 1: Signal 4,65, Hafenblau 6,20, Grün 5,02. */
export const KACHEL_FARBEN = {
  /** Signal-Orange, hsl(19 92% 42%) — die Farbe der KI. */
  signal: "#ce4709",
  /** Hafenblau, hsl(205 92% 34%) — der Rat. */
  primary: "#0764a6",
  /** Das Grün der Bebauungspläne auf der Stadtkarte (zugleich „Angenommen"). */
  green: "#15803d",
} as const;

export type KachelFarbe = keyof typeof KACHEL_FARBEN;

/** Der Farbwert zu einem Namen aus der Registry; Unbekanntes wird Hafenblau.
 *  (Der Server setzt die Vorgabe schon — der Rückfall fängt nur einen Namen
 *  ab, den dieser Build noch nicht kennt.) */
export function kachelFarbe(name: string | null | undefined): string {
  return (name && Object.prototype.hasOwnProperty.call(KACHEL_FARBEN, name))
    ? KACHEL_FARBEN[name as KachelFarbe]
    : KACHEL_FARBEN.primary;
}

/** „▶ 0:24" — die Länge eines Clips, auf ganze Sekunden gerundet.
 *  `null`, wenn sie niemand gemessen hat: dann steht auf der Kachel keine. */
export function formatDauer(sekunden: number | null | undefined): string | null {
  if (sekunden == null || !Number.isFinite(sekunden) || sekunden <= 0) return null;
  const gesamt = Math.max(1, Math.round(sekunden));
  const min = Math.floor(gesamt / 60);
  const sek = gesamt % 60;
  return `${min}:${String(sek).padStart(2, "0")}`;
}

/** Ausgeschrieben für Screenreader: „24 Sekunden", „1 Minute 5 Sekunden". */
export function dauerGesprochen(sekunden: number | null | undefined): string | null {
  if (sekunden == null || !Number.isFinite(sekunden) || sekunden <= 0) return null;
  const gesamt = Math.max(1, Math.round(sekunden));
  const min = Math.floor(gesamt / 60);
  const sek = gesamt % 60;
  const teile: string[] = [];
  if (min) teile.push(`${min} ${min === 1 ? "Minute" : "Minuten"}`);
  if (sek || !min) teile.push(`${sek} ${sek === 1 ? "Sekunde" : "Sekunden"}`);
  return teile.join(" ");
}

/** Kacheln und „Außerdem"-Zeilen einer Ausgabe. Die Reihenfolge der Registry
 *  bleibt in beiden erhalten. */
export function aufteilen(highlights: Highlight[]): { kacheln: Highlight[]; nebenbei: Highlight[] } {
  return {
    kacheln: highlights.filter((h) => !h.aside),
    nebenbei: highlights.filter((h) => h.aside),
  };
}

/** Hat diese Ausgabe Kacheln? Dafür braucht jede Kachel ein Medium — die
 *  Registry verlangt alle oder keines (`test_releases.py`). Ohne fällt die
 *  Karte auf die Listenform zurück. */
export function mitKacheln(release: Release | undefined): boolean {
  if (!release) return false;
  const { kacheln } = aufteilen(release.highlights);
  return kacheln.length > 0 && release.highlights.every((h) => !!h.media);
}

/** Ein stabiler Schlüssel je Highlight — derselbe wie `ReleaseHighlight.id`
 *  in der App (`url#title`). Die Registry hat keine Kennung; Ziel und Titel
 *  ändern sich nach dem Release nicht mehr. */
export function highlightSchluessel(h: Pick<Highlight, "url" | "title">): string {
  return `${h.url}#${h.title}`;
}

/** Wie viele Kacheln schon angesehen sind. */
export function zaehleGesehen(kacheln: Highlight[], gesehen: ReadonlySet<string>): number {
  return kacheln.filter((h) => gesehen.has(highlightSchluessel(h))).length;
}

/** Die erste Kachel, die noch niemand angesehen hat — dort beginnt „Los".
 *  Sind alle gesehen, beginnt es vorn. */
export function ersteUngesehene(kacheln: Highlight[], gesehen: ReadonlySet<string>): number {
  const i = kacheln.findIndex((h) => !gesehen.has(highlightSchluessel(h)));
  return i < 0 ? 0 : i;
}

// ---------------------------------------------------------------------------
// Angesehen — je Gerät
// ---------------------------------------------------------------------------
//
// **Warum im Browser und nicht am Konto.** Die Hochwassermarke
// (`news_seen_version`) bleibt die eine Entscheidung, die am Konto hängt: ob
// die Karte überhaupt noch erscheint. Welche der drei Kacheln jemand schon
// angetippt hat, ist dagegen eine Lesehilfe auf DIESEM Gerät — dieselbe Sorte
// wie der Lesestand im Haushalt (`lib/haushalt-fortschritt.ts`). Sie verloren
// zu haben (privates Fenster, anderes Gerät) kostet einen Haken, keine Karte.
//
// **Wann eine Kachel als angesehen gilt:** sobald ihr Clip im Spieler
// aufgeschlagen wurde. Nicht erst am Ende des Clips — mit reduzierter Bewegung
// startet er gar nicht von selbst, und wer nach fünf Sekunden „Weiter" tippt,
// hat seine Entscheidung über diese Neuerung getroffen.

const SPEICHER_PREFIX = "ratslotse.neuigkeiten.gesehen.";

function speicher(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

/** Was auf diesem Gerät für diese Ausgabe schon angesehen ist. Ein gesperrter
 *  oder kaputter Speicher heißt: nichts — nie ein Fehler. */
export function gesehenLesen(version: string): Set<string> {
  try {
    const roh = speicher()?.getItem(SPEICHER_PREFIX + version);
    if (!roh) return new Set();
    const liste: unknown = JSON.parse(roh);
    return new Set(Array.isArray(liste) ? liste.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

/** Eine Kachel als angesehen merken; gibt den neuen Stand zurück (auch wenn
 *  der Speicher ihn nicht halten konnte — die Seite zeigt ihn trotzdem). */
export function gesehenMerken(version: string, schluessel: string): Set<string> {
  const stand = gesehenLesen(version);
  if (stand.has(schluessel)) return stand;
  stand.add(schluessel);
  try {
    speicher()?.setItem(SPEICHER_PREFIX + version, JSON.stringify([...stand]));
  } catch {
    // Privates Fenster oder voller Speicher: Der Haken gilt für diesen Besuch.
  }
  return stand;
}

/** „16/9" → 1,78; „1206/2622" → 0,46. Unlesbares wird 16:9 — die Form der
 *  Browser-Clips, die das Web bekommt. */
export function seitenVerhaeltnis(aspect: string | null | undefined): number {
  const [b, h] = (aspect ?? "").split("/").map((x) => Number(x.trim()));
  return Number.isFinite(b) && Number.isFinite(h) && b > 0 && h > 0 ? b / h : 16 / 9;
}

/** Was am Ende eines Clips passiert.
 *
 *  **Weiter zum nächsten — aber nur, wenn Bewegung nicht abgeschaltet ist**
 *  (DESIGNSPRACHE §7, „Story-Spieler"). Im Spieler ist das Weiterschalten die
 *  erwartete Grammatik: Ein Mensch hat ihn geöffnet, um die Clips zu sehen,
 *  die Balken oben zeigen, wann der nächste kommt, und gewechselt wird erst,
 *  wenn der laufende zu Ende ist — nichts wird unter dem Lesen weggezogen. Mit
 *  reduzierter Bewegung startet kein Clip von selbst, also schaltet auch keiner
 *  weiter. Nach dem letzten bleibt der Spieler stehen; ein Nebenbei-Clip steht
 *  allein. */
export function nachDemEnde(opts: { index: number; anzahl: number; ruhig: boolean; nebenbei: boolean }):
  "weiter" | "stehen" {
  const { index, anzahl, ruhig, nebenbei } = opts;
  if (ruhig || nebenbei) return "stehen";
  return index < anzahl - 1 ? "weiter" : "stehen";
}
