// Farben und Schriften der Clips — aus web/frontend/app/globals.css (hell)
// und app/layout.tsx. Die Clips sind immer hell (kern/releases.py, Media).
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadBricolage } from "@remotion/google-fonts/BricolageGrotesque";

// Nur die Schnitte, die gebraucht werden — sonst lädt jedes Bild über
// hundert Schriftdateien (Remotion warnt zu Recht).
export const INTER = loadInter("normal", { weights: ["400", "600", "700"], subsets: ["latin"] }).fontFamily;
export const BRICOLAGE = loadBricolage("normal", { weights: ["800"], subsets: ["latin"] }).fontFamily;
export const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

export const C = {
  bg: "hsl(204 45% 97.5%)",
  bg2: "hsl(206 45% 93%)",
  fg: "hsl(212 55% 11%)",
  muted: "hsl(207 18% 38.5%)",
  primary: "hsl(205 92% 34%)",
  signal: "hsl(19 92% 42%)",
  border: "hsl(208 32% 89%)",
  card: "#ffffff",
};

/** Die Farbe eines Highlights (kern/releases.py, `Highlight.farbe`). */
const FARBEN: Record<string, string> = {
  signal: C.signal,
  primary: C.primary,
  gruen: "hsl(150 55% 30%)",
};
export const farbe = (name?: string) => FARBEN[name ?? "primary"] ?? C.primary;
