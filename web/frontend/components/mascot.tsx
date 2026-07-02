import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MascotTheme } from "@/lib/mascot-theme";
import { mascotThemeLabel } from "@/lib/mascot-theme";

/**
 * „Lotti" — die Lotsenmöwe von Ratslotse (und ihre Familie).
 *
 * Handgezeichnetes Flat-SVG in der Markenpalette (Marine + Signal-Orange). Lotti
 * lotst durch die App: begrüßt im Onboarding, zeigt auf Neues, guckt bei leeren
 * Ergebnissen durchs Fernrohr und hält auf der 404 Ausschau.
 *
 * Neu: Lotti blinzelt und atmet (`animated`, Default an), kleidet sich je nach
 * Jahreszeit und trägt zu besonderen Tagen (Halloween, Weihnachten, Ostern,
 * Pride) ein passendes Outfit (`theme`, meist über <SeasonalMascot/> gesetzt).
 * Dazu gibt es Küken (<Chick/>) und die ganze Familie (<MascotFamily/>).
 *
 * Farben sind bewusst fix (Sticker-Prinzip) und funktionieren auf hellem wie
 * dunklem Grund. Animationen respektieren `prefers-reduced-motion` global.
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
  goldDark: "#D99A1F",
  blush: "#FFAD85",
  zzz: "#8CA6BC",
  // Outfit-Farben
  scarfWarm: "#E4572E",
  scarfCool: "#3D8FD1",
  leaf: "#E08A2B",
  leafDark: "#C56A16",
  flower: "#F6A5C0",
  flowerCore: "#F2B441",
  shades: "#1B2A3A",
  santa: "#D7263D",
  santaDark: "#B01d31",
  witch: "#2E2350",
  witchBand: "#8C5BD1",
  bunny: "#F4F7FA",
  bunnyPink: "#F6A5C0",
  egg: "#7FC8E8",
  eggDot: "#F6A5C0",
  pumpkin: "#F5872B",
  pumpkinStem: "#4E7A3A",
  snow: "#DCEAF6",
};

const PRIDE = ["#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787"];

/* ── Grundformen ─────────────────────────────────────────────────────────── */

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

/* ── Gesicht (etwas größere, glänzendere Kulleraugen = niedlicher) ────────── */

const EyeDot = ({ cx, cy, r = 8 }: { cx: number; cy: number; r?: number }) => (
  <>
    <circle cx={cx} cy={cy} r={r} fill={C.eye} />
    <circle cx={cx - 2.8} cy={cy - 3} r={3} fill="#fff" />
    <circle cx={cx + 2.4} cy={cy + 1.8} r={1.3} fill="#fff" opacity={0.85} />
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
    <path d="M73,97 C76.5,90 87.5,90 91,97" stroke={C.eye} strokeWidth={4.5} strokeLinecap="round" fill="none" />
    <path d="M109,97 C112.5,90 123.5,90 127,97" stroke={C.eye} strokeWidth={4.5} strokeLinecap="round" fill="none" />
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
    <EyeDot cx={82} cy={96} r={8} />
    <EyeDot cx={118} cy={97} r={6} />
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
    <ellipse cx={66} cy={110} rx={7} ry={4.6} fill={C.blush} opacity={0.55} />
    <ellipse cx={134} cy={110} rx={7} ry={4.6} fill={C.blush} opacity={0.55} />
  </>
);

/* ── Kopfbedeckung: Lotsenmütze (Standard) + Feiertags-Hüte ───────────────── */

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

/** Südwester (Fischer-Regenhut) — für Lottis Partner-Möwe in der Familie. */
const Souwester = ({ tilt = -4 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 52)`}>
    <ellipse cx={100} cy={57} rx={52} ry={13} fill={C.goldDark} />
    <path d="M64,57 C64,33 80,23 100,23 C120,23 136,33 136,57 C124,52 112,49.5 100,49.5 C88,49.5 76,52 64,57 Z" fill={C.gold} />
    <path d="M70,50 C79,46.5 89,44.8 100,44.8 C111,44.8 121,46.5 130,50" stroke={C.goldDark} strokeWidth={2} fill="none" strokeLinecap="round" />
  </g>
);

/** Lotsenmütze mit Regenbogen-Band (Pride). */
const CapPride = ({ tilt = -5 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 52)`}>
    <path d="M60,58 C60,34 77,22 100,22 C123,22 140,34 140,58 C128,52.5 114,50 100,50 C86,50 72,52.5 60,58 Z" fill={C.navy} />
    <g>
      {PRIDE.map((col, i) => (
        <path
          key={col}
          d={`M59,${55 + i * 1.9} C71.5,${49.5 + i * 1.9} 85,${46.8 + i * 1.9} 100,${46.8 + i * 1.9} C115,${46.8 + i * 1.9} 128.5,${49.5 + i * 1.9} 141,${55 + i * 1.9}`}
          stroke={col}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
        />
      ))}
    </g>
    <circle cx={100} cy={38} r={6} fill={C.gold} />
    <path d="M100,33 L101.8,36.2 L105,38 L101.8,39.8 L100,43 L98.2,39.8 L95,38 L98.2,36.2 Z" fill={C.navyDark} />
  </g>
);

const SantaHat = ({ tilt = -6 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 46)`}>
    <path d="M62,54 C66,30 82,18 104,18 C126,18 150,26 158,26 C150,40 132,50 104,50 C88,50 73,52 62,54 Z" fill={C.santa} />
    <path d="M62,54 C66,42 78,34 96,32 C86,40 78,48 74,55 C70,54 66,54 62,54 Z" fill={C.santaDark} opacity={0.6} />
    <path d="M58,52 C72,46 90,44 106,50 C104,58 92,61 78,60 C70,59 63,56 58,52 Z" fill="#FFFFFF" />
    <circle cx={160} cy={25} r={9} fill="#FFFFFF" />
  </g>
);

const WitchHat = ({ tilt = -4 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 44)`}>
    <path d="M52,52 C70,44 130,44 148,52 C140,58 120,61 100,61 C80,61 60,58 52,52 Z" fill={C.witch} />
    <path d="M100,10 C104,10 112,30 120,50 C112,53 88,53 80,50 C88,30 96,10 100,10 Z" fill={C.witch} />
    <path d="M83,45 C92,47.5 108,47.5 117,45 C116,48 114,50 112,51.5 C104,53 96,53 88,51.5 C86,50 84,48 83,45 Z" fill={C.witchBand} />
    <circle cx={106} cy={19} r={3.4} fill={C.witchBand} />
  </g>
);

/** Osterhasen-Ohren als Stirnband. */
const BunnyEars = ({ tilt = -3 }: { tilt?: number }) => (
  <g transform={`rotate(${tilt} 100 40)`}>
    <path d="M84,54 C78,40 76,20 82,8 C90,10 95,30 94,52 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1.4} />
    <path d="M116,54 C122,40 124,20 118,8 C110,10 105,30 106,52 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1.4} />
    <path d="M85,50 C82,40 81,25 84,14 C88,18 90,34 90,50 Z" fill={C.bunnyPink} />
    <path d="M115,50 C118,40 119,25 116,14 C112,18 110,34 110,50 Z" fill={C.bunnyPink} />
    <path d="M74,54 C86,49 114,49 126,54 C118,58 108,60 100,60 C92,60 82,58 74,54 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1.2} />
  </g>
);

/* ── Add-ons: Schal, Brille, Blume, Blatt, Fahne, gehaltene Dinge ─────────── */

const Sunglasses = () => (
  <g>
    <path d="M64,92 h72" stroke={C.shades} strokeWidth={3} strokeLinecap="round" />
    <ellipse cx={82} cy={97} rx={13} ry={11} fill={C.shades} />
    <ellipse cx={118} cy={97} rx={13} ry={11} fill={C.shades} />
    <path d="M95,95 h10" stroke={C.shades} strokeWidth={3} />
    <path d="M77,92 l4,4" stroke="#8FB6D6" strokeWidth={2.4} strokeLinecap="round" opacity={0.8} />
    <path d="M113,92 l4,4" stroke="#8FB6D6" strokeWidth={2.4} strokeLinecap="round" opacity={0.8} />
  </g>
);

const Scarf = ({ color }: { color: string }) => (
  <>
    <path d="M64,150 C76,162 124,162 136,150 C134,160 126,168 118,170 C112,158 88,158 82,170 C74,168 66,160 64,150 Z" fill={color} />
    <g className="lotti-scarf-tail">
      <path d="M116,166 C124,172 128,184 127,196 C120,196 112,190 110,180 C112,174 114,170 116,166 Z" fill={color} />
      <path d="M116,166 C120,169 123,173 125,178 C121,177 117,174 114,171 Z" fill="#000" opacity={0.08} />
    </g>
  </>
);

const FlowerOnCap = () => (
  <g transform="translate(133 40) rotate(12)">
    {[0, 72, 144, 216, 288].map((a) => (
      <ellipse key={a} cx={0} cy={-6} rx={4} ry={6} fill={C.flower} transform={`rotate(${a})`} />
    ))}
    <circle cx={0} cy={0} r={4} fill={C.flowerCore} />
  </g>
);

const FallingLeaf = () => (
  <g transform="translate(150 46)">
    <g className="lotti-sway">
      <path d="M0,0 C9,-7 18,-4 20,5 C11,9 2,9 -2,5 C-2,2 -1,1 0,0 Z" fill={C.leaf} />
      <path d="M-1,3.5 L17,4" stroke={C.leafDark} strokeWidth={1.5} strokeLinecap="round" />
    </g>
  </g>
);

/** Ohrenschützer, über der Mütze getragen: Bügel wölbt sich über die Kappe,
    Muscheln sitzen seitlich am Kopf (nicht vor den Augen). */
const Earmuffs = () => (
  <g>
    <path d="M57,90 C57,-6 143,-6 143,90" stroke={C.scarfCool} strokeWidth={5} fill="none" strokeLinecap="round" />
    <circle cx={57} cy={93} r={11} fill={C.scarfCool} />
    <circle cx={143} cy={93} r={11} fill={C.scarfCool} />
    <circle cx={57} cy={93} r={6} fill="#FFFFFF" opacity={0.85} />
    <circle cx={143} cy={93} r={6} fill="#FFFFFF" opacity={0.85} />
  </g>
);

const Snow = () => (
  <g fill={C.snow}>
    <circle cx={52} cy={44} r={2.4} /><circle cx={150} cy={54} r={2} />
    <circle cx={40} cy={92} r={2} /><circle cx={162} cy={104} r={2.4} />
    <circle cx={70} cy={30} r={1.6} /><circle cx={132} cy={30} r={1.6} />
  </g>
);

const PrideFlag = () => (
  <g>
    <rect x={160} y={44} width={3.4} height={72} rx={1.7} fill={C.navyDark} />
    <circle cx={161.7} cy={44} r={3} fill={C.gold} />
    <g transform="translate(163.4 47)">
      <g className="lotti-flag">
        {PRIDE.map((col, i) => (
          <rect key={col} x={0} y={i * 5} width={34} height={5} fill={col} />
        ))}
      </g>
    </g>
  </g>
);

const PumpkinHeld = () => (
  <g transform="translate(138 150)">
    <ellipse cx={0} cy={0} rx={15} ry={13} fill={C.pumpkin} />
    <path d="M-8,-10 Q0,-6 8,-10" stroke={C.beakDark} strokeWidth={1.6} fill="none" opacity={0.35} />
    <path d="M0,-13 C0,-9 0,-9 0,-6" stroke={C.pumpkinStem} strokeWidth={3} strokeLinecap="round" />
    <path d="M-6,2 l3,4 l3,-4 l3,4 Z" fill={C.navyDark} />
    <path d="M-6,-3 l3,-3 l3,3 Z" fill={C.navyDark} />
    <path d="M2,-3 l3,-3 l3,3 Z" fill={C.navyDark} />
  </g>
);

const EggHeld = () => (
  <g transform="translate(134 152)">
    <path d="M0,-15 C9,-15 14,-4 14,4 C14,12 8,17 0,17 C-8,17 -14,12 -14,4 C-14,-4 -9,-15 0,-15 Z" fill={C.egg} />
    <path d="M-13,0 C-6,-4 6,-4 13,0" stroke={C.eggDot} strokeWidth={2.6} fill="none" />
    <path d="M-12,8 C-5,4 6,4 12,8" stroke="#FFFFFF" strokeWidth={2.2} fill="none" opacity={0.8} />
    <circle cx={-5} cy={-6} r={2} fill={C.flower} />
    <circle cx={6} cy={-4} r={2} fill={C.flowerCore} />
  </g>
);

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
  <text x={146} y={60} fontFamily="var(--font-display), system-ui" fontSize={30} fontWeight={700} fill={C.beak}>?</text>
);

const Zzz = () => (
  <g fill={C.zzz} fontFamily="var(--font-display), system-ui" fontWeight={700}>
    <text x={140} y={56} fontSize={20}>z</text>
    <text x={154} y={42} fontSize={15}>z</text>
    <text x={164} y={31} fontSize={11}>z</text>
  </g>
);

/* ── Posen: Körper + Flügel + Gesicht (OHNE Kopfbedeckung — die kommt je nach
      Thema separat dazu, damit Feiertags-Hüte die Mütze ersetzen können). ─── */

type PoseParts = { body: React.ReactNode; capTilt: number };

function poseParts(pose: MascotPose, animated: boolean): PoseParts {
  const eyeCls = animated ? "lotti-eyes" : undefined;
  switch (pose) {
    case "point":
      return {
        capTilt: -4,
        body: (<><Tail /><Body /><WingLeft /><WingRightPoint /><Feet /><g className={eyeCls}><EyesHappy /></g><BeakSmile /><Blush /></>),
      };
    case "celebrate":
      return {
        capTilt: -8,
        body: (<><Tail /><WingRightWave /><Body /><g transform="scale(-1,1) translate(-200,0)"><WingRightWave /></g><Feet /><EyesJoy /><BeakOpen /><Blush /></>),
      };
    case "search":
      return {
        capTilt: -4,
        body: (<><Tail /><Body /><WingLeft /><Feet /><Spyglass /><BeakHm /><Blush /></>),
      };
    case "confused":
      return {
        capTilt: 9,
        body: (<><Tail /><Body /><WingLeft /><WingRightFolded /><Feet /><g className={eyeCls}><EyesPuzzled /></g><BeakHm /><Blush /><QuestionMark /></>),
      };
    case "sleep":
      return {
        capTilt: -14,
        body: (<><Tail /><Body /><WingLeft /><WingRightFolded /><Feet /><EyesSleep /><BeakHm /><Blush /><Zzz /></>),
      };
    case "wave":
    default:
      return {
        capTilt: -6,
        body: (<><Tail /><g className={animated ? "lotti-wave" : undefined}><WingRightWave /></g><Body /><WingLeft /><Feet /><g className={eyeCls}><EyesHappy /></g><BeakOpen /><Blush /></>),
      };
  }
}

/* ── Outfit: Kopfbedeckung + Add-ons je nach Thema ────────────────────────── */

export type MascotHat = "cap" | "souwester";

function Headwear({ theme, tilt, hat = "cap" }: { theme: MascotTheme | null; tilt: number; hat?: MascotHat }) {
  switch (theme?.holiday) {
    case "halloween": return <WitchHat tilt={tilt - 1} />;
    case "christmas": return <SantaHat tilt={tilt} />;
    case "easter": return <BunnyEars tilt={tilt} />;
    case "pride": return <CapPride tilt={tilt} />;
    default:
      return hat === "souwester" ? <Souwester tilt={tilt} /> : <Cap tilt={tilt} />;
  }
}

function Outfit({ theme }: { theme: MascotTheme | null }) {
  if (!theme) return null;
  const bits: React.ReactNode[] = [];
  // Feiertags-Add-ons (über der Jahreszeit).
  if (theme.holiday === "pride") bits.push(<PrideFlag key="flag" />);
  if (theme.holiday === "christmas") bits.push(<Scarf key="xmas-scarf" color={C.santaDark} />);
  if (theme.holiday === "halloween") bits.push(<PumpkinHeld key="pumpkin" />);
  if (theme.holiday === "easter") bits.push(<EggHeld key="egg" />);
  // Jahreszeit-Add-ons — nur ohne Feiertag, damit es nicht überladen wirkt.
  if (!theme.holiday) {
    if (theme.season === "spring") bits.push(<FlowerOnCap key="flower" />);
    if (theme.season === "summer") bits.push(<Sunglasses key="shades" />);
    if (theme.season === "autumn") { bits.push(<Scarf key="a-scarf" color={C.scarfWarm} />); bits.push(<FallingLeaf key="leaf" />); }
    if (theme.season === "winter") { bits.push(<Scarf key="w-scarf" color={C.scarfCool} />); bits.push(<Earmuffs key="muffs" />); bits.push(<Snow key="snow" />); }
  }
  return <>{bits}</>;
}

/* ── Lotti ────────────────────────────────────────────────────────────────── */

export function Mascot({
  pose = "wave",
  className,
  bob = false,
  animated = true,
  theme = null,
  hat = "cap",
  decorative = false,
  label,
}: {
  pose?: MascotPose;
  className?: string;
  /** Sanft schaukeln lassen (wie ein Boot in der Dünung). */
  bob?: boolean;
  /** Blinzeln, Atmen, Winken. Default an; global via prefers-reduced-motion aus. */
  animated?: boolean;
  /** Jahreszeit-/Feiertags-Outfit. Meist über <SeasonalMascot/> gesetzt. */
  theme?: MascotTheme | null;
  /** Kopfbedeckung ohne Feiertag: Lotsenmütze (Lotti) oder Südwester (Partner). */
  hat?: MascotHat;
  /** Rein dekorativ (z. B. in der Familien-Gruppe): fürs Screenreader unsichtbar. */
  decorative?: boolean;
  label?: string;
}) {
  const parts = poseParts(pose, animated);
  const aria = label ?? (theme ? `Lotti, die Lotsenmöwe, ${mascotThemeLabel(theme)}` : "Lotti, die Lotsenmöwe");
  return (
    <svg
      viewBox="0 0 200 200"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : aria}
      aria-hidden={decorative || undefined}
      className={cn("h-28 w-28 select-none", bob && "animate-bob", className)}
    >
      <g className={animated ? "lotti-breathe" : undefined}>
        {parts.body}
        <Headwear theme={theme} tilt={parts.capTilt} hat={hat} />
        <Outfit theme={theme} />
      </g>
    </svg>
  );
}

/* ── Küken (Lottis Familie) ───────────────────────────────────────────────── */

/** Mini-Weihnachtsmütze fürs Küken. */
const ChickSantaHat = () => (
  <g transform="translate(0 6) rotate(-8 60 38)">
    <path d="M38,44 C40,26 52,18 64,20 C76,22 84,30 86,42 Z" fill={C.santa} />
    <path d="M78,26 C86,20 92,20 95,25" stroke={C.santa} strokeWidth={7} strokeLinecap="round" fill="none" />
    <circle cx={97} cy={27} r={4.5} fill="#FFFFFF" />
    <path d="M37,42 C53,36 71,36 87,42" stroke="#FFFFFF" strokeWidth={6.5} strokeLinecap="round" fill="none" />
  </g>
);

/** Mini-Hasenohren fürs Küken. */
const ChickBunnyEars = () => (
  <g transform="rotate(-4 60 36)">
    <path d="M48,44 C44,32 43,18 47,8 C53,10 56,26 55,42 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1.2} />
    <path d="M72,44 C76,32 77,18 73,8 C67,10 64,26 65,42 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1.2} />
    <path d="M49,38 C47.5,30 47.3,21 49.3,14 C51.6,17 52.7,28 52.6,38 Z" fill={C.bunnyPink} />
    <path d="M71,38 C72.5,30 72.7,21 70.7,14 C68.4,17 67.3,28 67.4,38 Z" fill={C.bunnyPink} />
    <path d="M44,45 C53,41.5 67,41.5 76,45 C70,48.5 50,48.5 44,45 Z" fill={C.bunny} stroke={C.wingTip} strokeWidth={1} />
  </g>
);

/** Mini-Schal fürs Küken (Winter). */
const ChickScarf = () => (
  <>
    <path d="M32,86 C42,96 78,96 88,86 C86,93 80,98 73,100 C68,94 52,94 47,100 C40,98 34,93 32,86 Z" fill={C.scarfCool} />
    <g className="lotti-scarf-tail">
      <path d="M70,96 C75,101 77,109 76,116 C70,115 66,110 65,104 C66,101 68,98 70,96 Z" fill={C.scarfCool} />
    </g>
  </>
);

/** Winziger Regenbogen-Wimpel fürs Küken (Pride). */
const ChickPennant = () => (
  <g>
    <rect x={92} y={56} width={2.6} height={38} rx={1.3} fill={C.navyDark} />
    <circle cx={93.3} cy={56} r={2.2} fill={C.gold} />
    <g transform="translate(94.6 58)">
      <g className="lotti-flag">
        {PRIDE.map((col, i) => (
          <rect key={col} x={0} y={i * 2.4} width={17} height={2.4} fill={col} />
        ))}
      </g>
    </g>
  </g>
);

/** Feiertags-/Jahreszeit-Accessoire fürs Küken — bewusst sparsamer als bei Lotti. */
function ChickOutfit({ theme }: { theme: MascotTheme | null }) {
  if (!theme) return null;
  if (theme.holiday === "christmas") return <ChickSantaHat />;
  if (theme.holiday === "easter") return <ChickBunnyEars />;
  if (theme.holiday === "pride") return <ChickPennant />;
  if (!theme.holiday && theme.season === "winter") return <ChickScarf />;
  return null;
}

/**
 * Ein kleines Möwenküken — runder, flauschiger, riesige Kulleraugen, mit einer
 * kecken Federtolle statt Mütze. `hop` lässt es hüpfen; `theme` zieht ihm zu
 * Weihnachten/Ostern/Pride/Winter ein Mini-Accessoire an.
 */
export function Chick({
  className,
  hop = false,
  animated = true,
  tone = "orange",
  theme = null,
  decorative = false,
  label = "Ein Möwenküken",
}: {
  className?: string;
  hop?: boolean;
  animated?: boolean;
  /** Schnabel-/Füßchen-Ton, damit die Geschwister sich leicht unterscheiden. */
  tone?: "orange" | "gold";
  theme?: MascotTheme | null;
  /** Rein dekorativ (z. B. in der Familien-Gruppe): fürs Screenreader unsichtbar. */
  decorative?: boolean;
  label?: string;
}) {
  const beak = tone === "gold" ? C.gold : C.beak;
  const beakDark = tone === "gold" ? C.goldDark : C.beakDark;
  return (
    <svg
      viewBox="0 0 120 120"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative || undefined}
      className={cn("h-16 w-16 select-none", hop && "lotti-hop", className)}
    >
      <g className={animated ? "lotti-breathe" : undefined}>
        {/* Füßchen */}
        <path d="M48,104 C42,110 39,112 36,113 C41,116 48,116 52,112 Z" fill={beakDark} />
        <path d="M72,104 C78,110 81,112 84,113 C79,116 72,116 68,112 Z" fill={beakDark} />
        {/* Flügelchen */}
        <path d="M30,66 C22,74 20,86 24,96 C33,100 42,97 46,90 C40,82 34,74 30,66 Z" fill={C.wing} />
        <path d="M90,66 C98,74 100,86 96,96 C87,100 78,97 74,90 C80,82 86,74 90,66 Z" fill={C.wing} />
        {/* Körper (schön rund) */}
        <ellipse cx={60} cy={74} rx={34} ry={32} fill={C.body} />
        <path d="M34,88 C42,98 52,102 60,102 C68,102 78,98 86,88 C80,99 70,105 60,105 C50,105 40,99 34,88 Z" fill={C.bodyShade} opacity={0.7} />
        {/* Federtolle */}
        <path d="M60,46 C57,38 58,32 62,28 C63,33 63,38 64,43 Z" fill={C.wingTip} />
        <path d="M60,46 C61,37 64,32 69,30 C67,35 64,40 62,45 Z" fill={C.wing} />
        {/* Augen (riesig) */}
        <g className={animated ? "lotti-eyes" : undefined}>
          <circle cx={48} cy={70} r={7.5} fill={C.eye} />
          <circle cx={72} cy={70} r={7.5} fill={C.eye} />
          <circle cx={45.6} cy={67.4} r={2.8} fill="#fff" />
          <circle cx={69.6} cy={67.4} r={2.8} fill="#fff" />
        </g>
        {/* Schnäbelchen */}
        <path d="M60,78 C64,78 67,80 67,82.5 C67,85 63.5,86.5 60,86.5 C56.5,86.5 53,85 53,82.5 C53,80 56,78 60,78 Z" fill={beak} />
        <path d="M55,85 C58,86 62,86 65,85 C63.5,87.5 56.5,87.5 55,85 Z" fill={beakDark} />
        {/* Bäckchen */}
        <ellipse cx={40} cy={82} rx={5} ry={3.4} fill={C.blush} opacity={0.55} />
        <ellipse cx={80} cy={82} rx={5} ry={3.4} fill={C.blush} opacity={0.55} />
        <ChickOutfit theme={theme} />
      </g>
    </svg>
  );
}

/**
 * Die ganze Familie: Lotti, ihre Partner-Möwe (mit Südwester) und die Küken
 * dazwischen. Für die Landing und fröhliche Leerzustände. Die Küken hüpfen
 * leicht versetzt; das Outfit-Thema gilt für alle.
 */
export function MascotFamily({
  className,
  theme = null,
  chicks = 3,
}: {
  className?: string;
  theme?: MascotTheme | null;
  chicks?: number;
}) {
  const delays = ["0s", "0.5s", "0.9s", "1.3s"];
  const aria = theme
    ? `Lotti, die Lotsenmöwe, mit ihrer Familie — ${mascotThemeLabel(theme)}`
    : "Lotti, die Lotsenmöwe, mit ihrer Familie";
  return (
    <div role="img" aria-label={aria} className={cn("flex items-end justify-center gap-1", className)}>
      <Mascot pose="wave" theme={theme} bob decorative className="h-32 w-32 sm:h-40 sm:w-40" />
      <div className="flex items-end gap-0.5">
        {Array.from({ length: Math.max(0, Math.min(4, chicks)) }).map((_, i) => (
          <span key={i} style={{ animationDelay: delays[i % delays.length] }} className="lotti-hop inline-block">
            <Chick tone={i % 2 === 0 ? "orange" : "gold"} theme={theme} decorative className={i === 1 ? "h-16 w-16" : "h-14 w-14"} />
          </span>
        ))}
      </div>
      {/* Partner-Möwe: gespiegelt, damit sie zu den Küken schaut. */}
      <span className="inline-block -scale-x-100">
        <Mascot pose="point" hat="souwester" theme={theme} decorative className="h-28 w-28 sm:h-36 sm:w-36" />
      </span>
    </div>
  );
}

/* ── Sprechblase mit Lotti ────────────────────────────────────────────────── */

/**
 * Sprechblase mit Lotti daneben — für Tipps und kleine Hinweise.
 * `side` bestimmt, wo Lotti steht (mobil bleibt sie oben links im Fluss).
 */
export function MascotTip({
  pose = "point",
  title,
  children,
  className,
  onDismiss,
}: {
  pose?: MascotPose;
  title?: string;
  children: React.ReactNode;
  className?: string;
  /** Zeigt ein kleines X in der Sprechblase (z. B. „Tipp ausblenden"). */
  onDismiss?: () => void;
}) {
  return (
    <div className={cn("flex items-end gap-3", className)}>
      <Mascot pose={pose} className="h-16 w-16 shrink-0" />
      <div className={cn("relative flex-1 rounded-2xl rounded-bl-sm border border-border bg-card p-3.5 shadow-sm", onDismiss && "pr-9")}>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Tipp ausblenden"
            className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
        {title && <p className="text-sm font-semibold text-foreground">{title}</p>}
        <div className={cn("text-sm leading-relaxed text-muted-foreground", title && "mt-0.5")}>{children}</div>
      </div>
    </div>
  );
}
