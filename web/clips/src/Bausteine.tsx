// Gemeinsame Bausteine der Clips: Hintergrund, Weg-Kette, Intro, Untertitel, Outro.
import React from "react";
import {
  AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { BRICOLAGE, C, INTER, MONO, farbe } from "./theme";
import type { Meta } from "./typen";

export const ease = Easing.bezier(0.33, 0, 0.2, 1);

/** 0 → 1 → 0 um einen Zeitpunkt: so stark „zieht“ ein Beat gerade. */
export function huelle(t: number, beat: number, vor: number, halt: number, nach: number) {
  const opt = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease } as const;
  return Math.min(
    interpolate(t, [beat - vor, beat], [0, 1], opt),
    interpolate(t, [beat + halt, beat + halt + nach], [1, 0], opt),
  );
}

export function Hintergrund() {
  return (
    <AbsoluteFill style={{
      background: `radial-gradient(1200px 700px at 15% 10%, #ffffff 0%, ${C.bg} 45%, ${C.bg2} 100%)`,
    }}>
      {/* die leisen Wellen der App */}
      <svg width="100%" height="100%" viewBox="0 0 1600 900" preserveAspectRatio="none"
        style={{ position: "absolute", opacity: 0.35 }}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <path key={i}
            d={`M0 ${160 + i * 130} C 300 ${130 + i * 130}, 500 ${190 + i * 130}, 800 ${160 + i * 130} S 1300 ${130 + i * 130}, 1600 ${160 + i * 130}`}
            fill="none" stroke="hsl(205 60% 80%)" strokeWidth="2" />
        ))}
      </svg>
    </AbsoluteFill>
  );
}

function Chip({ text, groesse }: { text: string; groesse: number }) {
  return (
    <div style={{
      padding: `${groesse * 0.32}px ${groesse * 0.7}px`, borderRadius: 999, background: C.card,
      border: `2px solid ${C.border}`, fontFamily: INTER, fontWeight: 600, fontSize: groesse, color: C.fg,
      boxShadow: "0 6px 18px -10px rgba(2,32,64,.35)", whiteSpace: "nowrap",
    }}>{text}</div>
  );
}

/** Der Weg zum Feature, Glied für Glied eingeblendet (ab Bild `ab`). */
export function Weg({ glieder, ab, groesse = 30 }: { glieder: string[]; ab: number; groesse?: number }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: groesse * 0.45, flexWrap: "wrap" }}>
      {glieder.map((g, i) => {
        const p = spring({ frame: frame - ab - i * 7, fps, config: { damping: 16, mass: 0.6 } });
        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <div style={{ opacity: p, fontFamily: INTER, fontSize: groesse, color: C.muted, fontWeight: 600 }}>›</div>
            )}
            <div style={{ opacity: p, transform: `translateY(${(1 - p) * 14}px)` }}>
              <Chip text={g} groesse={groesse} />
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

/** Titel, Nutzen und „So kommst du hin“. */
export function Intro({ meta, deckkraft, hoch = false }: { meta: Meta; deckkraft: number; hoch?: boolean }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lotti = spring({ frame, fps, config: { damping: 14 } });
  return (
    <AbsoluteFill style={{
      opacity: deckkraft, padding: hoch ? "0 80px" : "0 150px", justifyContent: "center",
    }}>
      <div style={{ display: "flex", flexDirection: hoch ? "column" : "row", alignItems: hoch ? "flex-start" : "center", gap: hoch ? 30 : 60 }}>
        <Img src={staticFile(meta.lotti ?? "standbild-winkt.png")} style={{
          width: hoch ? 300 : 260, transform: `translateY(${(1 - lotti) * 40}px)`,
        }} />
        <div>
          <div style={{
            fontFamily: MONO, fontSize: hoch ? 36 : 22, letterSpacing: "0.14em", textTransform: "uppercase",
            color: farbe(meta.farbe), fontWeight: 700,
          }}>{meta.kicker}</div>
          <div style={{
            fontFamily: BRICOLAGE, fontWeight: 800, fontSize: hoch ? 128 : 104, color: C.fg, lineHeight: 1.02,
            marginTop: 10, opacity: spring({ frame: frame - 3, fps, config: { damping: 18 } }),
          }}>{meta.titel}</div>
          <div style={{ fontFamily: INTER, fontSize: hoch ? 52 : 36, color: C.muted, marginTop: hoch ? 18 : 12, lineHeight: 1.2 }}>{meta.untertitel}</div>
          {/* Ab drei Gliedern passt die Kette nicht mehr neben das Label. */}
          <div style={{
            marginTop: 34, display: "flex", gap: 18,
            flexDirection: hoch || (meta.weg.length > 2) ? "column" : "row",
            alignItems: hoch || (meta.weg.length > 2) ? "flex-start" : "center",
          }}>
            <div style={{ fontFamily: INTER, fontSize: hoch ? 40 : 24, color: C.muted, fontWeight: 600, whiteSpace: "nowrap" }}>So kommst du hin:</div>
            <Weg glieder={hoch && meta.ort !== "browser" ? meta.app : meta.weg} ab={14} groesse={hoch ? 46 : 26} />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

/** Der Schritt, der gerade dran ist — aus `say()` des Drehbuchs. */
export function Untertitel({ steps, t, farbeName, unten = 34, oben, breite = 1240, schrift = 30 }: {
  steps: { t: number; text: string }[]; t: number; farbeName?: string; unten?: number; breite?: number; schrift?: number;
  /** Statt unten oben stehen, so weit vom Rand (Hochformat: je Schritt). */
  oben?: (i: number) => number | null;
}) {
  const { fps } = useVideoConfig();
  const i = steps.reduce((acc, s, k) => (s.t <= t + 0.15 ? k : acc), -1);
  if (i < 0) return null;
  const p = spring({ frame: Math.round((t - steps[i].t) * fps), fps, config: { damping: 18, mass: 0.7 } });
  const top = oben?.(i) ?? null;
  return (
    <div style={{
      position: "absolute", left: 0, right: 0, display: "flex", justifyContent: "center",
      ...(top === null ? { bottom: unten } : { top }),
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 18, padding: "16px 30px 16px 16px", borderRadius: 999,
        background: "rgba(255,255,255,.97)", boxShadow: "0 18px 40px -16px rgba(2,32,64,.45)",
        border: `1px solid ${C.border}`, transform: `translateY(${(1 - p) * 26}px)`, opacity: p, maxWidth: breite,
      }}>
        <div style={{
          width: schrift * 1.55, height: schrift * 1.55, borderRadius: 999, background: farbe(farbeName), color: "#fff",
          display: "grid", placeItems: "center", fontFamily: BRICOLAGE, fontWeight: 800, fontSize: schrift * 0.88, flexShrink: 0,
        }}>{i + 1}</div>
        <div style={{ fontFamily: INTER, fontWeight: 600, fontSize: schrift, color: C.fg, lineHeight: 1.2 }}>{steps[i].text}</div>
        <div style={{ fontFamily: INTER, fontSize: schrift * 0.66, color: C.muted, marginLeft: 6, whiteSpace: "nowrap" }}>
          {i + 1}/{steps.length}
        </div>
      </div>
    </div>
  );
}

/** „So findest du es“ — Weg im Browser und in der App. */
export function Outro({ meta, ab, deckkraft, hoch = false }: { meta: Meta; ab: number; deckkraft: number; hoch?: boolean }) {
  const { fps } = useVideoConfig();
  const zeile = (titel: string, glieder: string[], verzug: number) => (
    <>
      <div style={{
        marginTop: hoch ? 40 : 28, fontFamily: INTER, fontSize: hoch ? 36 : 22, color: C.muted, fontWeight: 700,
        textTransform: "uppercase", letterSpacing: "0.1em",
      }}>{titel}</div>
      <div style={{ marginTop: hoch ? 18 : 12 }}><Weg glieder={glieder} ab={ab + Math.round(verzug * fps)} groesse={hoch ? 46 : 28} /></div>
    </>
  );
  return (
    <AbsoluteFill style={{ padding: hoch ? "0 80px" : "0 90px", justifyContent: hoch ? "flex-start" : "center", paddingTop: hoch ? 150 : 0 }}>
      <div style={{ width: hoch ? "auto" : 640, opacity: deckkraft, transform: `translateX(${(1 - deckkraft) * -30}px)` }}>
        <div style={{ fontFamily: BRICOLAGE, fontWeight: 800, fontSize: hoch ? 110 : 62, color: C.fg, lineHeight: 1.05 }}>
          So findest du es
        </div>
        {hoch ? (meta.ort === "browser" ? zeile("Im Browser", meta.weg, 0.3) : zeile("In der App", meta.app, 0.3)) : (
          <>
            {zeile("Im Browser", meta.weg, 0.3)}
            {zeile("In der App", meta.app, 0.6)}
          </>
        )}
      </div>
    </AbsoluteFill>
  );
}
