"use client";

// Der Rücklagen-Pfad (Labor 2.0, Entwurf „Rücklagen-Pfad“): „Reicht
// rechnerisch 2,7 Jahre“ wird eine Kurve — man sieht das Jahr, in dem die
// Rücklage rechnerisch kippt, und wie das eigene Szenario den Punkt
// verschiebt.
//
// ZWEI LINIEN, EIN MASSSTAB: grau der Pfad ohne Änderung, Hafenblau der mit
// Szenario; beide starten beim selben Bestand. Der Kipp-Punkt trägt Signal —
// er ist die eine Abweichungs-Aussage der Grafik (Designsprache: Signal nur
// für Deltas und Marker, nie als Fläche).
//
// Gezeichnet wird NUR über die Planjahre; dahinter wird nicht verlängert
// („für später liegen keine Planzahlen vor“ ist Teil der Aussage).

import type { RuecklagenPfad as Pfad } from "@/lib/haushalt-labor";

const B = 300, H = 74, OBEN = 6, UNTEN = 16;

export function RuecklagenPfadGrafik({ ohne, mit }: { ohne: Pfad; mit: Pfad }) {
  const years = ohne.punkte.map((p) => p.year);
  if (years.length < 2) return null;
  const startJahr = years[0] - 1;
  const x = (year: number) =>
    ((year - startJahr) / (years[years.length - 1] - startJahr)) * B;
  const y = (stand: number) =>
    OBEN + (1 - stand / ohne.start) * (H - OBEN - UNTEN);

  const linie = (p: Pfad) =>
    [`${x(startJahr)},${y(p.start)}`,
      ...p.punkte.map((pt) => `${x(pt.year)},${y(pt.stand)}`)].join(" ");
  const verschieden = mit.punkte.some(
    (pt, i) => Math.abs(pt.stand - ohne.punkte[i].stand) > 0.05);

  return (
    <svg viewBox={`0 0 ${B} ${H}`} className="mt-1 block w-full" aria-hidden>
      {/* Nulllinie: Hier ist die Rücklage aufgebraucht. */}
      <line x1="0" y1={y(0)} x2={B} y2={y(0)} strokeWidth="1"
        style={{ stroke: "hsl(var(--border))" }} />
      <polyline points={linie(ohne)} fill="none" strokeWidth="2"
        style={{ stroke: "var(--hh-aus-4)" }} />
      {verschieden && (
        <polyline points={linie(mit)} fill="none" strokeWidth="2.5"
          style={{ stroke: "hsl(var(--primary))" }} />
      )}
      {ohne.kippjahr != null && (
        <circle cx={x(ohne.kippjahr)} cy={y(0)} r="3"
          style={{ fill: "var(--hh-aus-4)" }} />
      )}
      {verschieden && mit.kippjahr != null && (
        <circle cx={x(mit.kippjahr)} cy={y(0)} r="3.5"
          style={{ fill: "hsl(var(--signal))" }} />
      )}
      {/* Achse: nur Anfang und Ende — mehr trägt die schmale Rail nicht. */}
      <text x="0" y={H - 2} className="font-mono" fontSize="9"
        style={{ fill: "hsl(var(--muted-foreground))" }}>{startJahr}</text>
      <text x={B} y={H - 2} textAnchor="end" className="font-mono" fontSize="9"
        style={{ fill: "hsl(var(--muted-foreground))" }}>{years[years.length - 1]}</text>
    </svg>
  );
}
