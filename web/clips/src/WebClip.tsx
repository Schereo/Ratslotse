// Ein Browser-Clip: Intro mit dem Weg, die Aufnahme im Fenster mit
// Adresszeile, Spotlight statt starkem Zoom, Schritt-Untertitel, Outro.
//
// Warum so (Tims Befund 07.10.2026): Die alten Clips fingen mittendrin an
// und zoomten 1,6× auf den Klick — man sah weder, wie man hinkommt, noch den
// Zusammenhang. Hier zoomt die Kamera höchstens 1,25×; was gemeint ist, hebt
// ein Spotlight hervor, das den Rest nur abdunkelt.
import React from "react";
import {
  AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { C, INTER } from "./theme";
import { Hintergrund, Intro, Outro, Untertitel, ease, huelle } from "./Bausteine";
import type { Beat, ClipProps } from "./typen";

export const INTRO = 2.2;   // Sekunden
export const OUTRO = 2.6;
const CHROME = 46;          // Höhe der Fensterleiste
const MAX_ZOOM = 0.25;      // 1 + 0,25

/** Die Aufnahme mit Kamera, Spotlight und Klick-Welle — in Pixeln der Aufnahme. */
function Aufnahme({ props, t }: { props: ClipProps; t: number }) {
  const { width: W, height: H, beats } = props.timeline;

  // Kamera: Bei einem Klick ändert sich die Seite gleich danach — der Zoom
  // geht deshalb früh zurück, damit die neue Seite im Ganzen zu sehen ist.
  // Ein Blick (`tap: false`) darf länger halten.
  // Eine Lupe zoomt NICHT — die Vergrößerung steht als Karte daneben.
  let gewicht = 0;
  let fokusBeat: Beat | null = null;
  for (const b of beats) {
    if (b.lupe) continue;
    const w = b.tap ? huelle(t, b.t, 0.7, 0.5, 0.9) : huelle(t, b.t, 0.7, 1.8, 0.9);
    if (w > gewicht) { gewicht = w; fokusBeat = b; }
  }
  const fokus = fokusBeat ?? { x: W / 2, y: H / 2 };
  const zoom = 1 + MAX_ZOOM * gewicht;

  // Spotlight: bei einem Klick sofort aus (sonst stünde es auf der alten
  // Stelle der neuen Seite und träfe eine fremde Zeile), bei einer Lupe so
  // lange wie sie.
  let spot = 0;
  let aktiv: Beat | null = null;
  for (const b of beats) {
    if (!b.box) continue;
    const w = b.lupe ? huelle(t, b.t, 0.3, b.lupe - 0.2, 0.3)
      : b.tap ? huelle(t, b.t, 0.6, 0.15, 0.3) : huelle(t, b.t, 0.5, 1.6, 0.5);
    if (w > spot) { spot = w; aktiv = b; }
  }
  const box = aktiv?.box ?? null;
  const pad = 8;

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
            borderRadius: 14, boxShadow: `0 0 0 4000px rgba(10, 28, 48, ${0.38 * spot})`,
            outline: `3px solid ${C.signal}`, opacity: spot,
          }} />
        )}
        {wellen.map((b, i) => {
          const p = (t - b.t) / 0.9;
          const r = 40 * (0.4 + p);
          return (
            <div key={i} style={{
              position: "absolute", left: b.x - r, top: b.y - r, width: 2 * r, height: 2 * r, borderRadius: "50%",
              border: `4px solid ${C.signal}`, opacity: 1 - p,
            }} />
          );
        })}
      </div>
    </div>
  );
}

/** Die Lupe: das Ziel vergrößert als Karte neben dem Original — in
 *  Koordinaten des ganzen Bildes (1600×900), damit sie über dem Fenster
 *  stehen darf. `fy/s` bilden die Aufnahme ins Bild ab. */
function Lupen({ props, t, fy, s }: { props: ClipProps; t: number; fy: number; s: number }) {
  const { width: W } = props.timeline;
  const { fps } = useVideoConfig();
  return (
    <>
      {/* Erst MIT dem Ereignis einblenden, nicht davor: Die Aufnahme läuft dem
          Geschehen ein paar Bilder hinterher — 0,3 s früher stand in der Lupe
          noch Lottis Begrüßung statt der Antwort (07.10.2026). */}
      {props.timeline.beats.filter((b) => b.lupe && b.box && t >= b.t && t < b.t + b.lupe + 0.3).map((b, i) => {
        const box = b.box!;
        const pad = 10;
        const bw = box.w + 2 * pad;
        const bh = box.h + 2 * pad;
        // So groß wie möglich, höchstens 2,4×, und es muss neben das Original passen.
        const f = Math.min(2.4, 780 / bw, 640 / bh);
        // Eine Lupe, die kaum vergrößert, ist nur eine zweite Kopie — dann
        // bleibt es beim Spotlight (das Drehbuch sollte enger zielen). Ab
        // 1,15× lohnt sie: Die Eckdaten von „Frag den Rat“ sind breit, und
        // schon 1,2× als hervortretende Karte machte sie lesbar.
        if (f < 1.15) return null;
        const kb = bw * f;
        const kh = bh * f;
        const links = b.x > W / 2;   // Ziel rechts → Karte links und umgekehrt
        const x = links ? 70 : 1600 - 70 - kb;
        const mitteY = fy + (box.y + box.h / 2) * s;
        const y = Math.max(40, Math.min(900 - 150 - kh, mitteY - kh / 2));
        const p = spring({ frame: Math.round((t - b.t) * fps), fps, config: { damping: 16, mass: 0.6 } });
        const weg = interpolate(t, [b.t + b.lupe! - 0.05, b.t + b.lupe! + 0.3], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const d = Math.min(p, weg);
        return (
          <div key={i} style={{
            position: "absolute", left: x, top: y, width: kb, height: kh, borderRadius: 18, overflow: "hidden",
            background: "#fff", opacity: d, transform: `scale(${0.92 + 0.08 * d})`,
            boxShadow: `0 30px 70px -20px rgba(2,32,64,.6), 0 0 0 3px ${C.signal}`,
          }}>
            <div style={{
              position: "absolute", left: -(box.x - pad) * f, top: -(box.y - pad) * f,
              width: props.timeline.width * f, height: props.timeline.height * f,
            }}>
              <OffthreadVideo src={staticFile(props.video)} muted
                style={{ width: props.timeline.width * f, height: props.timeline.height * f }} />
            </div>
          </div>
        );
      })}
    </>
  );
}

/** Fensterleiste mit der Adresse, die gerade offen ist. */
function Adresse({ props, t }: { props: ClipProps; t: number }) {
  const navs = props.timeline.navigations.filter((n) => n.t <= t);
  const url = (navs.length ? navs[navs.length - 1].url : props.timeline.startUrl)
    .replace(/^https?:\/\/[^/]+/, "ratslotse.de");
  const [host, ...rest] = url.split("/");
  return (
    <div style={{
      height: CHROME, display: "flex", alignItems: "center", gap: 14, padding: "0 18px",
      background: "#f3f6f9", borderBottom: `1px solid ${C.border}`,
    }}>
      <div style={{ display: "flex", gap: 8 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />)}
      </div>
      <div style={{
        flex: 1, maxWidth: 640, margin: "0 auto", height: 30, borderRadius: 9, background: "#fff",
        border: `1px solid ${C.border}`, display: "flex", alignItems: "center", padding: "0 14px",
        fontFamily: INTER, fontSize: 16, color: C.muted, whiteSpace: "nowrap", overflow: "hidden",
      }}>
        <span style={{ color: C.fg }}>{host}</span><span>/{rest.join("/")}</span>
      </div>
      <div style={{ width: 60 }} />
    </div>
  );
}

export const WebClip: React.FC<ClipProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { width: W, height: H, duration } = props.timeline;

  // Das Fenster füllt die Höhe; die Aufnahme steht fast 1:1.
  const innenH = 900 - 2 * 26 - CHROME;
  const s = innenH / H;
  const fensterW = W * s;
  const fensterH = innenH + CHROME;

  const tv = t - INTRO;   // Zeit in der Aufnahme
  const ende = INTRO + duration;
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease } as const;
  const rein = interpolate(t, [INTRO - 0.55, INTRO + 0.1], [0, 1], opt);
  const raus = interpolate(t, [ende, ende + 0.6], [0, 1], opt);
  const introWeg = interpolate(t, [INTRO - 0.5, INTRO], [1, 0], opt);

  return (
    <AbsoluteFill style={{ fontFamily: INTER }}>
      <Hintergrund />
      {t < INTRO + 0.1 && <Intro meta={props} deckkraft={introWeg} />}

      {t >= INTRO - 0.6 && (
        <div style={{
          position: "absolute", left: (1600 - fensterW) / 2, top: (900 - fensterH) / 2,
          width: fensterW, height: fensterH, borderRadius: 18, overflow: "hidden", background: C.card,
          boxShadow: "0 40px 90px -40px rgba(2,32,64,.55), 0 0 0 1px rgba(2,32,64,.08)",
          transform: `translateX(${raus * 380}px) scale(${0.94 + 0.06 * rein - 0.42 * raus})`, opacity: rein,
        }}>
          <Adresse props={props} t={Math.max(0, Math.min(tv, duration))} />
          <div style={{ position: "relative", width: fensterW, height: innenH }}>
            <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${s})`, transformOrigin: "0 0" }}>
              <Sequence from={Math.round(INTRO * fps)} durationInFrames={Math.round(duration * fps)} layout="none">
                <Aufnahme props={props} t={tv} />
              </Sequence>
              {t >= ende && (
                <Img src={staticFile(props.letztesBild)} style={{ position: "absolute", inset: 0, width: W, height: H }} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Lupen über allem außer dem Untertitel — in derselben Zeit wie die Aufnahme */}
      <Sequence from={Math.round(INTRO * fps)} durationInFrames={Math.round(duration * fps)} layout="none">
        <Lupen props={props} t={tv} fy={(900 - fensterH) / 2 + CHROME} s={s} />
      </Sequence>
      {tv >= 0 && tv < duration && <Untertitel steps={props.timeline.steps} t={tv} farbeName={props.farbe} />}
      {t >= ende && <Outro meta={props} ab={Math.round((ende + 0.3) * fps)} deckkraft={raus} />}
    </AbsoluteFill>
  );
};
