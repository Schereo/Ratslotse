// Das Titelbild einer Kachel in der Karte „Neu bei Ratslotse“ (Hochformat
// 1080×1200). OHNE Schrift: Titel und Zeile setzt die Karte selbst darüber
// (unten, auf ruhigem Grund in der Farbe des Highlights) — in den Bildern
// stünden sie doppelt und ließen sich nicht übersetzen oder ändern.
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { farbe } from "./theme";
import type { TitelbildProps } from "./typen";

export const Titelbild: React.FC<TitelbildProps> = (p) => {
  const f = farbe(p.farbe);
  // Ausschnitt: die obere linke Ecke der Aufnahme, so breit, dass das Fenster
  // 920 px misst — man erkennt die Seite, ohne Kleingedrucktes zu brauchen.
  const fensterB = 920;
  const fensterH = 690;
  return (
    <AbsoluteFill style={{
      background: `radial-gradient(900px 700px at 30% 15%, color-mix(in srgb, ${f} 55%, white) 0%, ${f} 70%)`,
    }}>
      <svg width="1080" height="1200" style={{ position: "absolute", opacity: 0.18 }}>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <path key={i} d={`M0 ${120 + i * 160} C 260 ${90 + i * 160}, 520 ${150 + i * 160}, 1080 ${110 + i * 160}`}
            fill="none" stroke="#fff" strokeWidth="3" />
        ))}
      </svg>
      <div style={{
        position: "absolute", left: 80, top: 90, width: fensterB, height: fensterH, borderRadius: 22,
        overflow: "hidden", background: "#fff", transform: "rotate(-2.5deg)",
        boxShadow: "0 50px 90px -30px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.4)",
      }}>
        <div style={{ height: 40, background: "#f3f6f9", display: "flex", alignItems: "center", gap: 8, padding: "0 16px" }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />)}
        </div>
        <Img src={staticFile(p.bild)} style={{
          width: fensterB, height: (p.hoehe / p.breite) * fensterB, display: "block",
        }} />
      </div>
      {p.lotti && (
        <Img src={staticFile(p.lotti)} style={{ position: "absolute", right: 40, top: 560, width: 300 }} />
      )}
    </AbsoluteFill>
  );
};
