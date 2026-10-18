// Ein Clip im Hochformat, randlos: die Aufnahme füllt das ganze Bild.
//
// Warum ohne Telefon-Rahmen (07.10.2026): Am Telefon steht der Clip im
// Spieler gut halb so breit wie der Bildschirm. Ein Rahmen im Clip hätte den
// Inhalt noch einmal auf gut die Hälfte verkleinert — Text in einem Viertel
// seiner echten Größe. Randlos steht er in derselben Größe wie die Seite, die
// er zeigt. Gilt für den Browser am Telefon (`ort: "browser"`) und die App.
//
// Ohne Lupe: Der Inhalt ist hier schon so groß wie im Original. Was gemeint
// ist, hebt das Spotlight hervor; der Untertitel steht oben oder unten, je
// nachdem, wo im Schritt getippt wird — nie über dem, worum es geht.
import React from "react";
import {
  AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { C, INTER } from "./theme";
import { Hintergrund, Intro, Outro, Untertitel, ease, huelle } from "./Bausteine";
import type { Beat, ClipProps } from "./typen";

export const INTRO_HOCH = 2.4;
export const OUTRO_HOCH = 2.6;
export const BREITE_HOCH = 1080;

/** Bildhöhe zur Aufnahme: gleiche Proportion, auf 10 gerundet — der
 *  Schnitt rendert mit `--scale=0.8`, und h264 braucht eine gerade Zahl. */
export function hoeheHoch(w: number, h: number) {
  return Math.round((BREITE_HOCH * h) / w / 10) * 10;
}

function Aufnahme({ props, t }: { props: ClipProps; t: number }) {
  const { width: W, height: H, beats } = props.timeline;
  // Kaum Kamera: ein Hauch Zoom bei einem Blick, keiner beim Tipp (danach
  // wechselt die Seite, und die soll man im Ganzen sehen).
  let gewicht = 0;
  let fokus = { x: W / 2, y: H / 2 };
  for (const b of beats) {
    if (b.tap || b.lupe) continue;
    const w = huelle(t, b.t, 0.6, 1.6, 0.8);
    if (w > gewicht) { gewicht = w; fokus = { x: b.x, y: b.y }; }
  }
  const zoom = 1 + 0.08 * gewicht;

  let spot = 0;
  let aktiv: Beat | null = null;
  for (const b of beats) {
    if (!b.box) continue;
    const w = b.lupe ? huelle(t, b.t, 0.3, b.lupe - 0.2, 0.3)
      // Beim Tipp mit dem Tipp aus: Gleich danach lädt die neue Seite, und
      // ein Rahmen über einer leeren Fläche sah aus wie ein Fehler.
      : b.tap ? huelle(t, b.t, 0.5, 0.0, 0.12) : huelle(t, b.t, 0.5, 1.6, 0.5);
    if (w > spot) { spot = w; aktiv = b; }
  }
  const box = aktiv?.box ?? null;
  // Maße in Pixeln der Aufnahme: Der Browser liefert CSS-Pixel (390 breit),
  // der Simulator echte (1206) — Welle und Rahmen wachsen mit.
  const k = W / 390;
  const pad = 5 * k;
  const wellen = beats.filter((b) => b.tap && t >= b.t && t < b.t + 0.9);

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div style={{
        position: "absolute", width: W, height: H,
        transformOrigin: `${fokus.x}px ${fokus.y}px`, transform: `scale(${zoom})`,
      }}>
        <OffthreadVideo src={staticFile(props.video)} style={{ width: W, height: H }} muted />
        {box && spot > 0.01 && (
          <div style={{
            position: "absolute", left: box.x - pad, top: box.y - pad, width: box.w + 2 * pad, height: box.h + 2 * pad,
            borderRadius: 10 * k, boxShadow: `0 0 0 ${3000 * k}px rgba(10, 28, 48, ${0.4 * spot})`,
            outline: `${2 * k}px solid ${C.signal}`, opacity: spot,
          }} />
        )}
        {wellen.map((b, i) => {
          const p = (t - b.t) / 0.9;
          const r = 22 * k * (0.45 + p);
          return (
            <div key={i} style={{
              position: "absolute", left: b.x - r, top: b.y - r, width: 2 * r, height: 2 * r, borderRadius: "50%",
              border: `${3 * k}px solid ${C.signal}`, background: "rgba(255,255,255,.22)", opacity: 1 - p,
            }} />
          );
        })}
      </div>
    </div>
  );
}

export const HochClip: React.FC<ClipProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps, height: HOEHE } = useVideoConfig();
  const t = frame / fps;
  const { width: W, height: H, duration, beats, steps } = props.timeline;
  const s = BREITE_HOCH / W;
  const tv = t - INTRO_HOCH;
  const ende = INTRO_HOCH + duration;
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease } as const;
  const rein = interpolate(t, [INTRO_HOCH - 0.5, INTRO_HOCH + 0.15], [0, 1], opt);
  const raus = interpolate(t, [ende, ende + 0.7], [0, 1], opt);
  const introWeg = interpolate(t, [INTRO_HOCH - 0.5, INTRO_HOCH], [1, 0], opt);

  // Untertitel je Schritt oben oder unten: unten, sobald im Schritt etwas
  // im oberen Drittel angetippt oder angesehen wird — sonst oben (unten
  // stehen am Telefon Tab-Leiste und Lotti, und die sind oft das Ziel).
  const oben = (i: number) => {
    const von = steps[i]?.t ?? 0;
    const bis = steps[i + 1]?.t ?? Infinity;
    const imSchritt = beats.filter((b) => b.t >= von - 0.2 && b.t < bis);
    const obenGetippt = imSchritt.some((b) => (b.box ? b.box.y + b.box.h / 2 : b.y) < H * 0.34);
    return obenGetippt ? null : 70;
  };

  // Im Outro schrumpft das letzte Bild nach unten, der Weg steht darüber.
  const kleinS = 1 - 0.5 * raus;
  const kleinY = raus * HOEHE * 0.2;
  const p = spring({ frame: frame - Math.round((INTRO_HOCH - 0.5) * fps), fps, config: { damping: 18 } });

  return (
    <AbsoluteFill style={{ fontFamily: INTER }}>
      <Hintergrund />
      {t < INTRO_HOCH + 0.1 && <Intro meta={props} deckkraft={introWeg} hoch />}

      {t >= INTRO_HOCH - 0.6 && (
        <div style={{
          position: "absolute", left: 0, top: 0, width: BREITE_HOCH, height: HOEHE, overflow: "hidden",
          opacity: rein, borderRadius: 64 * (1 - p) + 54 * raus,
          transform: `translateY(${kleinY}px) scale(${(0.92 + 0.08 * p) * kleinS})`,
          boxShadow: raus > 0 ? "0 50px 100px -40px rgba(2,32,64,.6)" : undefined,
        }}>
          <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${s})`, transformOrigin: "0 0" }}>
            <Sequence from={Math.round(INTRO_HOCH * fps)} durationInFrames={Math.round(duration * fps)} layout="none">
              <Aufnahme props={props} t={tv} />
            </Sequence>
            {t >= ende && <Img src={staticFile(props.letztesBild)} style={{ position: "absolute", inset: 0, width: W, height: H }} />}
          </div>
        </div>
      )}

      {tv >= 0 && tv < duration && (
        <Untertitel steps={steps} t={tv} farbeName={props.farbe} unten={170} oben={oben} breite={1020} schrift={46} />
      )}
      {t >= ende && <Outro meta={props} ab={Math.round((ende + 0.3) * fps)} deckkraft={raus} hoch />}
    </AbsoluteFill>
  );
};
