import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * „Lotti" — die Lotsenmöwe von Ratslotse.
 *
 * Handgezeichnetes Flat-SVG in der Markenpalette (Marine + Signal-Orange).
 * Lotti lotst durch die App: begrüßt im Onboarding, zeigt auf Neues, guckt
 * bei leeren Suchergebnissen durchs Fernrohr und hält auf der 404 Ausschau.
 * Die Farben sind bewusst fix (Sticker-Prinzip) und funktionieren auf hellem
 * wie dunklem Grund.
 */
export type MascotPose = "wave" | "point" | "celebrate" | "search" | "confused" | "sleep";

const C = {
  body: "#FFFFFF",
  bodyShade: "#E4EEF6",
  wing: "#C7D6E4",
  wingTip: "#8CA6BC",
  navy: "#143A5C",
  navyDark: "#0E2B46",
  visor: "#0A1F33",
  eye: "#122A40",
  beak: "#F66623",
  beakDark: "#D9531E",
  gold: "#F2B441",
  blush: "#FFAD85",
  zzz: "#8CA6BC",
};

const Body = () => (
  <>
    <path d="M100,58 C134,58 154,88 154,124 C154,158 131,180 100,180 C69,180 46,158 46,124 C46,88 66,58 100,58 Z" fill={C.body} />
    <path d="M67,158 C76,168 88,173 100,173 C112,173 124,168 133,158 C126,171 114,180 100,180 C86,180 74,171 67,158 Z" fill={C.bodyShade} opacity={0.8} />
  </>
);

const Tail = () => (
  <>
    <path d="M52,140 C40,146 34,156 33,166 C44,164 54,158 60,150 Z" fill={C.wing} />
    <path d="M40,158 C36,162 34,164 33,166 C38,165 43,163 47,160 Z" fill={C.wingTip} />
  </>
);

const Feet = () => (
  <>
    <path d="M78,176 C70,184 66,186 62,187 C68,190 78,190 84,185 Z" fill={C.beakDark} />
    <path d="M122,176 C130,184 134,186 138,187 C132,190 122,190 116,185 Z" fill={C.beakDark} />
  </>
);

const WingLeft = () => (
  <>
    <path d="M56,102 C42,112 36,130 40,148 C52,156 66,154 74,144 C66,132 60,118 56,102 Z" fill={C.wing} />
    <path d="M42,138 C42,142 41,145 40,148 C46,152 53,153 60,151 C54,148 47,144 42,138 Z" fill={C.wingTip} />
  </>
);

/** Rechter Flügel gespiegelt angelegt. */
const WingRightFolded = () => (
  <g transform="scale(-1,1) translate(-200,0)">
    <WingLeft />
  </g>
);

const WingRightWave = () => (
  <>
    <path d="M144,108 C158,92 166,74 166,56 C154,58 142,68 136,82 C138,92 141,101 144,108 Z" fill={C.wing} />
    <path d="M162,64 C164,61 165,58 166,56 C160,57 154,60 149,64 C153,65 158,65 162,64 Z" fill={C.wingTip} />
  </>
);

const WingRightPoint = () => (
  <>
    <path d="M140,110 C158,104 172,102 184,104 C180,112 170,120 158,122 C151,119 145,115 140,110 Z" fill={C.wing} />
    <path d="M178,106 C180,105 182,104 184,104 C182,108 179,112 175,115 C176,112 177,109 178,106 Z" fill={C.wingTip} />
  </>
);

const EyeDot = ({ cx, cy, r = 7 }: { cx: number; cy: number; r?: number }) => (
  <>
    <circle cx={cx} cy={cy} r={r} fill={C.eye} />
    <circle cx={cx - 2.6} cy={cy - 2.6} r={2.4} fill="#fff" />
  </>
);

const EyesHappy = () => (
  <>
    <EyeDot cx={82} cy={96} />
    <EyeDot cx={118} cy={96} />
  </>
);

const EyesJoy = () => (
  <>
    <path d="M74,96 C77,90 87,90 90,96" stroke={C.eye} strokeWidth={4} strokeLinecap="round" fill="none" />
    <path d="M110,96 C113,90 123,90 126,96" stroke={C.eye} strokeWidth={4} strokeLinecap="round" fill="none" />
  </>
);

const EyesSleep = () => (
  <>
    <path d="M74,98 C77,102 87,102 90,98" stroke={C.eye} strokeWidth={4} strokeLinecap="round" fill="none" />
    <path d="M110,98 C113,102 123,102 126,98" stroke={C.eye} strokeWidth={4} strokeLinecap="round" fill="none" />
  </>
);

const EyesPuzzled = () => (
  <>
    <EyeDot cx={82} cy={96} r={7.5} />
    <EyeDot cx={118} cy={97} r={5.5} />
  </>
);

const BeakSmile = () => (
  <>
    <path d="M100,105 C107,105 111,108 111,111 C111,114.2 106,116.4 100,116.4 C94,116.4 89,114.2 89,111 C89,108 93,105 100,105 Z" fill={C.beak} />
    <path d="M93.5,115 C97.5,116.6 102.5,116.6 106.5,115 C104.8,118.4 95.2,118.4 93.5,115 Z" fill={C.beakDark} />
  </>
);

const BeakOpen = () => (
  <>
    <path d="M100,105 C107,105 111,108 111,111 C111,114 106,116 100,116 C94,116 89,114 89,111 C89,108 93,105 100,105 Z" fill={C.beak} />
    <path d="M100,116 C104.5,116 108.5,115.2 110,113.6 C109.4,118.6 105.4,122 100,122 C94.6,122 90.6,118.6 90,113.6 C91.5,115.2 95.5,116 100,116 Z" fill={C.beakDark} />
  </>
);

const BeakHm = () => (
  <>
    <path d="M100,106 C106.5,106 110.5,108.6 110.5,111 C110.5,113.6 105.5,115.4 100,115.4 C94.5,115.4 89.5,113.6 89.5,111 C89.5,108.6 93.5,106 100,106 Z" fill={C.beak} />
    <path d="M96.5,115.2 C98.8,115.8 101.2,115.8 103.5,115.2 C102.2,117.4 97.8,117.4 96.5,115.2 Z" fill={C.beakDark} />
  </>
);

const Blush = () => (
  <>
    <ellipse cx={67} cy={110} rx={6} ry={4} fill={C.blush} opacity={0.5} />
    <ellipse cx={133} cy={110} rx={6} ry={4} fill={C.blush} opacity={0.5} />
  </>
);

/** Lotsenmütze (Prinz-Heinrich) mit Kompass-Abzeichen — sitzt hoch, Augen bleiben frei. */
const Cap = ({ tilt = -5 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 52)`}>
    <path d="M60,58 C60,34 77,22 100,22 C123,22 140,34 140,58 C128,52.5 114,50 100,50 C86,50 72,52.5 60,58 Z" fill={C.navy} />
    <path d="M59,55 C71.5,49.5 85,46.8 100,46.8 C115,46.8 128.5,49.5 141,55 C142.5,59 142.5,62.5 141,66 C128.5,60.5 115,57.8 100,57.8 C85,57.8 71.5,60.5 59,66 C57.5,62.5 57.5,59 59,55 Z" fill={C.navyDark} />
    <path d="M72,52.5 C80.5,56 90,57.8 100,57.8 C110,57.8 119.5,56 128,52.5 C123,60.5 112,65 100,65 C88,65 77,60.5 72,52.5 Z" fill={C.visor} />
    <path d="M66,54 C77,49.6 88.5,47.5 100,47.5 C111.5,47.5 123,49.6 134,54" stroke={C.gold} strokeWidth={2.2} fill="none" strokeLinecap="round" />
    <circle cx={100} cy={38} r={6} fill={C.gold} />
    <path d="M100,33 L101.8,36.2 L105,38 L101.8,39.8 L100,43 L98.2,39.8 L95,38 L98.2,36.2 Z" fill={C.navyDark} />
  </g>
);

/** Fernrohr überm rechten Auge, rechter Flügel stützt von unten. */
const Spyglass = () => (
  <>
    <path d="M76,96 C79,93 85,93 88,96" stroke={C.eye} strokeWidth={4} strokeLinecap="round" fill="none" />
    <path d="M132,110 C142,106 150,104 158,104 C155,111 148,117 139,119 C136,116 134,113 132,110 Z" fill={C.wing} />
    <g transform="rotate(-18 118 96)">
      <rect x={112} y={89.5} width={40} height={13} rx={5.5} fill={C.navy} />
      <rect x={148} y={87.5} width={9} height={17} rx={3.5} fill={C.navyDark} />
      <rect x={136} y={88.5} width={3} height={15} fill={C.gold} />
      <circle cx={118} cy={96} r={8.5} fill={C.navyDark} />
      <circle cx={118} cy={96} r={5.5} fill="#BFE3F7" />
      <circle cx={116.2} cy={94.2} r={1.8} fill="#fff" />
    </g>
  </>
);

const QuestionMark = () => (
  <text x={146} y={60} fontFamily="var(--font-display), system-ui" fontSize={30} fontWeight={700} fill={C.beak}>
    ?
  </text>
);

const Zzz = () => (
  <g fill={C.zzz} fontFamily="var(--font-display), system-ui" fontWeight={700}>
    <text x={140} y={56} fontSize={20}>z</text>
    <text x={154} y={42} fontSize={15}>z</text>
    <text x={164} y={31} fontSize={11}>z</text>
  </g>
);

const POSES: Record<MascotPose, React.ReactNode> = {
  wave: (
    <>
      <Tail /><WingRightWave /><Body /><WingLeft /><Feet />
      <Cap tilt={-6} /><EyesHappy /><BeakOpen /><Blush />
    </>
  ),
  point: (
    <>
      <Tail /><Body /><WingLeft /><WingRightPoint /><Feet />
      <Cap tilt={-4} /><EyesHappy /><BeakSmile /><Blush />
    </>
  ),
  celebrate: (
    <>
      <Tail /><WingRightWave /><Body />
      <g transform="scale(-1,1) translate(-200,0)"><WingRightWave /></g>
      <Feet /><Cap tilt={-8} /><EyesJoy /><BeakOpen /><Blush />
    </>
  ),
  search: (
    <>
      <Tail /><Body /><WingLeft /><Feet />
      <Cap tilt={-4} /><Spyglass /><BeakHm /><Blush />
    </>
  ),
  confused: (
    <>
      <Tail /><Body /><WingLeft /><WingRightFolded /><Feet />
      <Cap tilt={9} /><EyesPuzzled /><BeakHm /><Blush /><QuestionMark />
    </>
  ),
  sleep: (
    <>
      <Tail /><Body /><WingLeft /><WingRightFolded /><Feet />
      <Cap tilt={-14} /><EyesSleep /><BeakHm /><Blush /><Zzz />
    </>
  ),
};

export function Mascot({
  pose = "wave",
  className,
  bob = false,
  label = "Lotti, die Lotsenmöwe",
}: {
  pose?: MascotPose;
  className?: string;
  /** Sanft schaukeln lassen (wie ein Boot in der Dünung). */
  bob?: boolean;
  label?: string;
}) {
  return (
    <svg
      viewBox="0 0 200 200"
      role="img"
      aria-label={label}
      className={cn("h-28 w-28 select-none", bob && "animate-bob", className)}
    >
      {POSES[pose]}
    </svg>
  );
}

/**
 * Sprechblase mit Lotti daneben — für Tipps und kleine Hinweise.
 * `side` bestimmt, wo Lotti steht (mobil bleibt sie oben links im Fluss).
 */
export function MascotTip({
  pose = "point",
  title,
  children,
  className,
}: {
  pose?: MascotPose;
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-end gap-3", className)}>
      <Mascot pose={pose} className="h-16 w-16 shrink-0" />
      <div className="relative flex-1 rounded-2xl rounded-bl-sm border border-border bg-card p-3.5 shadow-sm">
        {title && <p className="text-sm font-semibold text-foreground">{title}</p>}
        <div className={cn("text-sm leading-relaxed text-muted-foreground", title && "mt-0.5")}>{children}</div>
      </div>
    </div>
  );
}
