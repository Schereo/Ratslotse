// Ein App-Clip: Intro mit dem Weg in der App, die Aufnahme im Telefon-Rahmen,
// Tipp-Welle und leichter Zoom, Schritt-Untertitel unter dem Telefon, Outro.
// Hochformat 1080×1920 — so steht er in der App-Karte (kern/releases.py,
// `media_ios`).
import React from "react";
import {
  AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { C, INTER } from "./theme";
import { Hintergrund, Intro, Outro, Untertitel, ease, huelle } from "./Bausteine";
import type { ClipProps } from "./typen";

export const INTRO_TEL = 2.2;
export const OUTRO_TEL = 2.6;

const SCHIRM_H = 1440;   // Höhe des Bildschirms im Rahmen
const RAND = 18;         // Rahmenbreite

function Aufnahme({ props, t }: { props: ClipProps; t: number }) {
  const { width: W, height: H, beats } = props.timeline;
  let gewicht = 0;
  let fokus = { x: W / 2, y: H / 2 };
  for (const b of beats) {
    const w = huelle(t, b.t, 0.6, 0.6, 0.8);
    if (w > gewicht) { gewicht = w; fokus = { x: b.x, y: b.y }; }
  }
  const zoom = 1 + 0.15 * gewicht;
  const wellen = beats.filter((b) => b.tap && t >= b.t && t < b.t + 0.9);
  const r0 = W * 0.06;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div style={{ position: "absolute", width: W, height: H, transformOrigin: `${fokus.x}px ${fokus.y}px`, transform: `scale(${zoom})` }}>
        <OffthreadVideo src={staticFile(props.video)} style={{ width: W, height: H }} muted />
        {wellen.map((b, i) => {
          const p = (t - b.t) / 0.9;
          const r = r0 * (0.5 + p);
          return (
            <div key={i} style={{
              position: "absolute", left: b.x - r, top: b.y - r, width: 2 * r, height: 2 * r, borderRadius: "50%",
              border: `${Math.round(W * 0.008)}px solid ${C.signal}`, background: "rgba(255,255,255,.18)", opacity: 1 - p,
            }} />
          );
        })}
      </div>
    </div>
  );
}

export const TelefonClip: React.FC<ClipProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { width: W, height: H, duration } = props.timeline;
  const s = SCHIRM_H / H;
  const schirmB = W * s;
  const tv = t - INTRO_TEL;
  const ende = INTRO_TEL + duration;
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease } as const;
  const rein = interpolate(t, [INTRO_TEL - 0.55, INTRO_TEL + 0.1], [0, 1], opt);
  const raus = interpolate(t, [ende, ende + 0.6], [0, 1], opt);
  const introWeg = interpolate(t, [INTRO_TEL - 0.5, INTRO_TEL], [1, 0], opt);
  const oben = 90;

  return (
    <AbsoluteFill style={{ fontFamily: INTER }}>
      <Hintergrund />
      {t < INTRO_TEL + 0.1 && <Intro meta={props} deckkraft={introWeg} hoch />}

      {t >= INTRO_TEL - 0.6 && (
        <div style={{
          position: "absolute", left: (1080 - schirmB) / 2 - RAND, top: oben - RAND,
          width: schirmB + 2 * RAND, height: SCHIRM_H + 2 * RAND, borderRadius: 86, background: "#0d1620",
          boxShadow: "0 50px 100px -40px rgba(2,32,64,.6)", opacity: rein,
          transform: `translateY(${raus * 520}px) scale(${0.94 + 0.06 * rein - 0.4 * raus})`,
        }}>
          <div style={{ position: "absolute", left: RAND, top: RAND, width: schirmB, height: SCHIRM_H, borderRadius: 70, overflow: "hidden", background: "#fff" }}>
            <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${s})`, transformOrigin: "0 0" }}>
              <Sequence from={Math.round(INTRO_TEL * fps)} durationInFrames={Math.round(duration * fps)} layout="none">
                <Aufnahme props={props} t={tv} />
              </Sequence>
              {t >= ende && <Img src={staticFile(props.letztesBild)} style={{ position: "absolute", inset: 0, width: W, height: H }} />}
            </div>
          </div>
        </div>
      )}

      {tv >= 0 && tv < duration && (
        <Untertitel steps={props.timeline.steps} t={tv} farbeName={props.farbe} unten={150} breite={1000} schrift={38} />
      )}
      {t >= ende && <Outro meta={props} ab={Math.round((ende + 0.3) * fps)} deckkraft={raus} hoch />}
    </AbsoluteFill>
  );
};
