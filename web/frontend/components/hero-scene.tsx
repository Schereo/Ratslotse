"use client";

import { SeasonalFamily } from "@/components/seasonal-mascot";

/**
 * Ersetzt die alte 3D-Oldenburg-Karte im Landing-Hero: eine freundliche
 * Hafenszene (Himmel, Sonne, Wolken, Wasser) mit Lotti und ihren Küken auf dem
 * Steg. Rein dekorativ; Lotti trägt automatisch das Jahreszeit-/Feiertags-Outfit.
 */
export function HeroScene() {
  return (
    <div className="relative mx-auto aspect-[4/3] w-full max-w-lg overflow-hidden rounded-[2rem] border border-border bg-gradient-to-b from-sky-200/80 via-sky-100/60 to-primary/15 shadow-lifted dark:from-slate-800 dark:via-slate-800/70 dark:to-primary/20">
      {/* Himmel: Sonne + driftende Wolken */}
      <div className="absolute right-8 top-7 h-16 w-16 rounded-full bg-gradient-to-br from-amber-200 to-signal/70 blur-[1px]" aria-hidden />
      <svg viewBox="0 0 400 300" className="absolute inset-0 h-full w-full" aria-hidden preserveAspectRatio="xMidYMid slice">
        <g className="animate-cloud-drift" fill="#FFFFFF" opacity={0.85}>
          <ellipse cx={90} cy={64} rx={34} ry={18} />
          <ellipse cx={118} cy={58} rx={26} ry={16} />
          <ellipse cx={62} cy={60} rx={22} ry={14} />
        </g>
        <g className="animate-cloud-drift-slow" fill="#FFFFFF" opacity={0.7}>
          <ellipse cx={300} cy={98} rx={30} ry={15} />
          <ellipse cx={324} cy={92} rx={22} ry={13} />
        </g>
        {/* Wasser */}
        <path d="M0,214 C60,204 120,224 200,214 C280,204 340,224 400,214 L400,300 L0,300 Z" fill="hsl(var(--primary))" opacity={0.16} />
        <path d="M0,232 C70,224 130,242 200,232 C270,222 330,242 400,232 L400,300 L0,300 Z" fill="hsl(var(--primary))" opacity={0.22} />
        {/* kleiner Steg */}
        <g>
          <rect x={150} y={230} width={100} height={9} rx={2} fill="#B5895A" />
          <rect x={158} y={239} width={7} height={22} fill="#946E42" />
          <rect x={235} y={239} width={7} height={22} fill="#946E42" />
        </g>
        {/* Boje */}
        <g className="animate-bob" style={{ transformOrigin: "330px 210px" }}>
          <circle cx={330} cy={210} r={9} fill="#E4572E" />
          <path d="M321,210 h18" stroke="#fff" strokeWidth={3} />
          <rect x={328} y={196} width={4} height={8} rx={2} fill="#0E2B46" />
        </g>
      </svg>

      {/* Familie auf dem Steg */}
      <div className="absolute inset-x-0 bottom-[16%] flex justify-center">
        <SeasonalFamily chicks={3} />
      </div>

      {/* sanfter Vignette-Rahmen */}
      <div className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-inset ring-white/20" aria-hidden />
    </div>
  );
}
