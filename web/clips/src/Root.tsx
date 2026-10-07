// Die Kompositionen. Gerendert wird über scripts/release_clips.py, das die
// Aufnahme samt Zeitachse in ein eigenes public-Verzeichnis legt und die
// Props übergibt; die Vorgaben hier sind nur fürs Remotion Studio.
import React from "react";
import { Composition, Still } from "remotion";
import { INTRO, OUTRO, WebClip } from "./WebClip";
import { Titelbild } from "./Titelbild";
import { INTRO_TEL, OUTRO_TEL, TelefonClip } from "./TelefonClip";
import type { ClipProps, TitelbildProps } from "./typen";

const FPS = 30;

const meta = {
  kicker: "Neu in Ratslotse 3.0", titel: "Mein Viertel", untertitel: "Was sich vor deiner Haustür tut",
  weg: ["Seitenleiste", "Mein Viertel"], app: ["Mehr", "Mein Viertel"], farbe: "gruen",
};
const beispiel: ClipProps = {
  ...meta, video: "roh.mp4", letztesBild: "letztes-bild.png",
  timeline: { width: 1280, height: 800, duration: 10, beats: [], steps: [], navigations: [], startUrl: "http://localhost/dashboard" },
};

export const Root: React.FC = () => (
  <>
    <Composition
      id="WebClip"
      component={WebClip}
      width={1600}
      height={900}
      fps={FPS}
      durationInFrames={Math.round((INTRO + beispiel.timeline.duration + OUTRO) * FPS)}
      defaultProps={beispiel}
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.round((INTRO + props.timeline.duration + OUTRO) * FPS),
      })}
    />
    <Composition
      id="TelefonClip"
      component={TelefonClip}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={Math.round((INTRO_TEL + beispiel.timeline.duration + OUTRO_TEL) * FPS)}
      defaultProps={beispiel}
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.round((INTRO_TEL + props.timeline.duration + OUTRO_TEL) * FPS),
      })}
    />
    <Still
      id="Titelbild"
      component={Titelbild}
      width={1080}
      height={1200}
      defaultProps={{ ...meta, bild: "letztes-bild.png", breite: 1280, hoehe: 800, lotti: "standbild-zeigt-links.png" } as TitelbildProps}
    />
  </>
);
