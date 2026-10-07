// Was scripts/release_clips.py an Remotion übergibt (`--props`).

export type Box = { x: number; y: number; w: number; h: number };

/** Ein Klick (`tap`) oder Blick des Drehbuchs — Zeit in Sekunden ab `begin()`,
 *  Ort in Pixeln der Aufnahme. `box` ist der Umriss des Ziels. */
export type Beat = {
  t: number; x: number; y: number; tap: boolean; box: Box | null;
  /** Lupe: so viele Sekunden steht das Ziel vergrößert daneben. */
  lupe?: number;
};

export type Zeitachse = {
  width: number;
  height: number;
  duration: number;
  beats: Beat[];
  /** `say()` des Drehbuchs: ab `t` steht dieser Schritt als Untertitel. */
  steps: { t: number; text: string }[];
  navigations: { t: number; url: string }[];
  startUrl: string;
};

export type Meta = {
  kicker: string;
  titel: string;
  untertitel: string;
  /** Der Weg zum Feature im Browser, z. B. ["Seitenleiste", "Mein Viertel"]. */
  weg: string[];
  /** Derselbe Weg in der App. */
  app: string[];
  /** `Highlight.farbe` — signal | primary | gruen */
  farbe?: string;
  /** Lotti im Intro (Datei aus web/frontend/public/lotti/). */
  lotti?: string;
  /** Hochformat: Wo die Aufnahme spielt — „browser" (am Telefon) zeigt `weg`,
   *  „app" zeigt `app`. Vorgabe: app. */
  ort?: "browser" | "app";
};

export type ClipProps = Meta & {
  video: string;          // Rohaufnahme im public-Verzeichnis des Laufs
  letztesBild: string;    // ihr letztes Bild (steht im Outro)
  timeline: Zeitachse;
};

export type TitelbildProps = Meta & {
  bild: string;           // ein Bild aus der Aufnahme
  breite: number;         // seine Größe in Pixeln
  hoehe: number;
};
