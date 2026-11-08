// Der Mauszeiger, in jedes Bild neu gezeichnet — aus der Bahn, die der
// Recorder mitschreibt (web/frontend/scripts/release-clip.mjs).
//
// Bis 11/2026 war der Zeiger Teil der Seite und kam mit der Aufnahme: Die
// erwischte ihn nur an einzelnen Stellen, er sprang (Tims Befund zur 3.0.0:
// „hakelig“). Hier steht er in jedem Bild genau dort, wo ihn die Kurve
// hinlegt — unabhängig davon, wie oft Chrome ein Bild geliefert hat.
import React from "react";
import { interpolate } from "remotion";
import type { Zeitachse } from "./typen";

/** Minimaler Ruck — dieselbe Kurve wie `ruck` im Recorder. */
export function ruck(p: number) {
  return p * p * p * (10 - 15 * p + 6 * p * p);
}

/** Wo der Zeiger zur Zeit `t` steht; `null`, solange er noch nicht da ist. */
export function zeigerOrt(punkte: Zeitachse["pointer"], t: number): { x: number; y: number } | null {
  if (!punkte?.length || t < punkte[0].t) return null;
  for (let i = 0; i + 1 < punkte.length; i++) {
    const a = punkte[i];
    const b = punkte[i + 1];
    if (t >= b.t) continue;
    const p = b.t > a.t ? ruck((t - a.t) / (b.t - a.t)) : 1;
    return { x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p };
  }
  const z = punkte[punkte.length - 1];
  return { x: z.x, y: z.y };
}

/** 0 = losgelassen, 1 = gedrückt — mit kurzem Übergang statt eines Sprungs. */
export function druck(spannen: Zeitachse["presses"], t: number) {
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  let d = 0;
  for (const s of spannen ?? []) {
    d = Math.max(d, Math.min(interpolate(t, [s.a, s.a + 0.06], [0, 1], opt), interpolate(t, [s.b, s.b + 0.09], [1, 0], opt)));
  }
  return d;
}

/** Die Spitze des Pfeils im 26-px-Kasten (Pfad beginnt bei 5/2,5 von 24). */
const SPITZE = { x: (5 * 26) / 24, y: (2.5 * 26) / 24 };

/** Der Pfeil in Pixeln der Aufnahme (CSS-Pixel der Seite), `t` ist die Zeit
 *  in der Aufnahme. Kurz vor ihrem Ende blendet er aus, damit er nicht mit
 *  dem Schnitt ins Outro verschwindet. */
export function Zeiger({ timeline, t }: { timeline: Zeitachse; t: number }) {
  const ort = zeigerOrt(timeline.pointer, t);
  if (!ort) return null;
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const deckkraft = Math.min(
    interpolate(t, [timeline.pointer![0].t, timeline.pointer![0].t + 0.18], [0, 1], opt),
    interpolate(t, [timeline.duration - 0.3, timeline.duration - 0.05], [1, 0], opt),
  );
  // Die Spitze sitzt genau auf dem Punkt, und das Drücken schrumpft den
  // Pfeil um sie herum — sie bleibt auf dem Ziel.
  const s = 1 - 0.18 * druck(timeline.presses, t);
  return (
    <div style={{
      position: "absolute", left: 0, top: 0, width: 26, height: 26, opacity: deckkraft, pointerEvents: "none",
      transformOrigin: `${SPITZE.x}px ${SPITZE.y}px`,
      transform: `translate(${ort.x - SPITZE.x}px, ${ort.y - SPITZE.y}px) scale(${s})`,
    }}>
      <svg viewBox="0 0 24 24" width="26" height="26" style={{ filter: "drop-shadow(0 2px 5px rgba(0,0,0,.45))", overflow: "visible" }}>
        <path d="M5 2.5 L5 19.2 L9.3 15.2 L12.1 21.6 L15.2 20.2 L12.4 14 L18.3 13.6 Z"
          fill="#111827" stroke="#ffffff" strokeWidth="1.7" strokeLinejoin="round" />
      </svg>
    </div>
  );
}
