// Die Karte der Nähe — die 36 Paarabstände als 2D-Projektion (MDS, gerechnet
// in analyse.py). Statisches, serverseitig gerendertes SVG: kein Client-JS,
// keine Library. Je näher zwei Punkte, desto öfter sind sich die Programme
// einig; dünne Linien verbinden Paare mit ≥ 70 % Übereinstimmung.
//
// WICHTIG (ehrliche Karte): Die Achsen bedeuten nichts — sie sind das
// Rechenergebnis der Abstände, keine politischen Dimensionen. Deshalb keine
// Achsenbeschriftung, und die Bildunterschrift sagt es ausdrücklich.

import type { KartenKante, KartenPunkt } from "@/lib/kommunalwahl-types";

const B = 640;
const H = 400;
const RAND_X = 64;
const RAND_Y = 52;

function sx(x: number): number {
  return RAND_X + ((x + 1) / 2) * (B - 2 * RAND_X);
}
function sy(y: number): number {
  // y positiv = oben
  return H - RAND_Y - ((y + 1) / 2) * (H - 2 * RAND_Y);
}

export function Landkarte({ punkte, kanten }: { punkte: KartenPunkt[]; kanten: KartenKante[] }) {
  const von = Object.fromEntries(punkte.map((p) => [p.slug, p]));
  const beschreibung = punkte.map((p) => p.kurz).join(", ");
  return (
    <figure className="overflow-hidden rounded-2xl border border-border bg-card">
      <svg
        viewBox={`0 0 ${B} ${H}`}
        role="img"
        aria-label={`Karte der Nähe mit den Positionen von ${beschreibung} — je näher zwei Punkte, desto öfter stimmen die Programme überein.`}
        className="block h-auto w-full"
      >
        {/* Kanten der nächsten Paare — Stärke folgt der Übereinstimmung */}
        {kanten.map((k) => {
          const a = von[k.a];
          const b = von[k.b];
          if (!a || !b) return null;
          return (
            <line
              key={`${k.a}|${k.b}`}
              x1={sx(a.x)}
              y1={sy(a.y)}
              x2={sx(b.x)}
              y2={sy(b.y)}
              stroke="currentColor"
              strokeWidth={1 + ((k.wert - 70) / 30) * 1.6}
              className="text-foreground"
              opacity={0.1 + ((k.wert - 70) / 30) * 0.16}
            />
          );
        })}
        {punkte.map((p) => {
          // Beschriftung normalerweise unter den Punkt — außer direkt darunter
          // sitzt ein Nachbar, dann nach oben ausweichen (BB-OL über BSW).
          const nachbarUnten = punkte.some(
            (q) => q.slug !== p.slug && Math.abs(q.x - p.x) < 0.28 && p.y - q.y > 0 && p.y - q.y < 0.5,
          );
          const abstand = p.landesprogramm ? 30 : 24;
          return (
            <g key={p.slug}>
              {p.landesprogramm && (
                <circle
                  cx={sx(p.x)}
                  cy={sy(p.y)}
                  r={15}
                  fill="none"
                  strokeDasharray="3 3"
                  strokeWidth={1.4}
                  className="stroke-amber-600 dark:stroke-amber-400"
                />
              )}
              <circle
                cx={sx(p.x)}
                cy={sy(p.y)}
                r={9}
                className="kw-fill"
                style={{ "--kw-f": p.farbe, "--kw-fd": p.farbeDunkel } as React.CSSProperties}
              />
              <text
                x={sx(p.x)}
                y={sy(p.y) + (nachbarUnten ? -(abstand - 8) : abstand)}
                textAnchor="middle"
                className="fill-current text-foreground"
                fontSize={12}
                fontWeight={600}
              >
                {p.kurz}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border bg-background/60 px-5 py-3 text-[11.5px] text-muted-foreground">
        <span>
          Je näher zwei Punkte, desto öfter stimmen die Programme überein. Linien verbinden Paare mit
          mindestens 70 %.
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full border border-dashed border-amber-600 dark:border-amber-400" />
          BSW: Landesprogramm ohne Oldenburg-Bezug
        </span>
        <span className="ml-auto">
          Die Achsen bedeuten nichts — nur die Abstände zählen.
        </span>
      </figcaption>
    </figure>
  );
}
