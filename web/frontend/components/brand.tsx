import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Die Ratslotse-Marke: Lotti, die Lotsenmöwe, als App-Icon-Marke.
 * Inline-SVG (statt PNG), damit sie auf jeder Größe scharf bleibt und keinen
 * weißen Kasten im Dark Mode braucht. Gleiche Geometrie wie app/icon.png und
 * das Maskottchen in components/mascot.tsx.
 */
export function BrandMark({ className }: { className?: string }) {
  // Eindeutige Gradient-ID, falls die Marke mehrfach auf einer Seite steht.
  const id = React.useId();
  const bg = `bg-${id}`;
  return (
    <svg viewBox="0 0 64 64" role="img" aria-label="Ratslotse" className={cn("h-9 w-9 shrink-0", className)}>
      <defs>
        <linearGradient id={bg} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0B72B8" />
          <stop offset="1" stopColor="#0A3D66" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14" fill={`url(#${bg})`} />
      {/* Kopf */}
      <circle cx="32" cy="40" r="18" fill="#FFFFFF" />
      {/* Augen */}
      <circle cx="25.5" cy="39" r="3.4" fill="#122A40" />
      <circle cx="24.3" cy="37.8" r="1.25" fill="#fff" />
      <circle cx="38.5" cy="39" r="3.4" fill="#122A40" />
      <circle cx="37.3" cy="37.8" r="1.25" fill="#fff" />
      {/* Wangen */}
      <ellipse cx="19.5" cy="45" rx="2.6" ry="1.8" fill="#FFAD85" opacity="0.55" />
      <ellipse cx="44.5" cy="45" rx="2.6" ry="1.8" fill="#FFAD85" opacity="0.55" />
      {/* Schnabel */}
      <path d="M32,43.5 C35.2,43.5 37.2,44.9 37.2,46.2 C37.2,47.7 35,48.7 32,48.7 C29,48.7 26.8,47.7 26.8,46.2 C26.8,44.9 28.8,43.5 32,43.5 Z" fill="#F66623" />
      <path d="M29.2,48.1 C31,48.8 33,48.8 34.8,48.1 C34,49.9 30,49.9 29.2,48.1 Z" fill="#D9531E" />
      {/* Lotsenmütze */}
      <g transform="rotate(-4 32 22)">
        <path d="M17.5,26.5 C17.5,15.5 24.5,10 32,10 C39.5,10 46.5,15.5 46.5,26.5 C42,24.3 37,23.2 32,23.2 C27,23.2 22,24.3 17.5,26.5 Z" fill="#143A5C" />
        <path d="M17,25 C21.7,22.8 26.8,21.7 32,21.7 C37.2,21.7 42.3,22.8 47,25 C47.7,26.7 47.7,28.3 47,30 C42.3,27.8 37.2,26.7 32,26.7 C26.8,26.7 21.7,27.8 17,30 C16.3,28.3 16.3,26.7 17,25 Z" fill="#0E2B46" />
        <path d="M22.5,26.8 C25.5,28.2 28.7,28.9 32,28.9 C35.3,28.9 38.5,28.2 41.5,26.8 C39.7,30.2 36.2,32.1 32,32.1 C27.8,32.1 24.3,30.2 22.5,26.8 Z" fill="#0A1F33" />
        <path d="M19.5,24.2 C23.5,22.5 27.7,21.7 32,21.7 C36.3,21.7 40.5,22.5 44.5,24.2" stroke="#F2B441" strokeWidth="1.1" fill="none" strokeLinecap="round" />
        <circle cx="32" cy="16.5" r="2.6" fill="#F2B441" />
        <path d="M32,14.4 L32.8,15.7 L34.1,16.5 L32.8,17.3 L32,18.6 L31.2,17.3 L29.9,16.5 L31.2,15.7 Z" fill="#0E2B46" />
      </g>
    </svg>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="font-display text-lg font-bold tracking-tight text-foreground">Ratslotse</span>
    </div>
  );
}
