"use client";

// Der Countdown zur Wahl. Die Seiten sind statisch vorgerendert — ein zur
// Bauzeit eingebackener Wert wäre nach ein paar Tagen falsch, deshalb rechnet
// der Client nach dem Mounten selbst. Bis dahin steht der Bauzeit-Wert da
// (suppressHydrationWarning), der höchstens um die Tage seit dem Deploy abweicht.

import { useEffect, useState } from "react";

const WAHLTAG_UTC = Date.UTC(2026, 8, 13); // 13.09.2026

export function tageBis(jetzt = new Date()): number {
  const heute = Date.UTC(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate());
  return Math.max(0, Math.ceil((WAHLTAG_UTC - heute) / 86_400_000));
}

export function TageZahl() {
  const [tage, setTage] = useState(() => tageBis());
  useEffect(() => setTage(tageBis()), []);
  return <span suppressHydrationWarning>{tage}</span>;
}

/** Signal-Badge im Hero — das einzige Element in Signal-Orange (Handoff). */
export function CountdownBadge({ kompakt = false }: { kompakt?: boolean }) {
  const [vorbei, setVorbei] = useState(false);
  useEffect(() => setVorbei(tageBis() <= 0), []);
  if (vorbei) return null;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-signal px-3.5 py-1 text-[12px] font-semibold text-signal-foreground sm:text-[13px]">
      Noch <TageZahl /> Tage — {kompakt ? "wählen gehen" : "am 13. September wählen gehen"}
    </span>
  );
}

/** Dunkle Countdown-Karte in der Seitenleiste (Design 2a, Rail). */
export function CountdownKarte() {
  return (
    <div className="mb-3.5 rounded-[14px] bg-foreground px-4 py-3.5 text-background">
      <p className="font-display text-[28px] font-bold tabular-nums leading-none">
        <TageZahl /> <span className="text-[13px] font-medium opacity-70">Tage</span>
      </p>
      <p className="mt-1 text-xs opacity-70">bis zur Ratswahl am 13.09.</p>
    </div>
  );
}

/** Nach der Wahl wird der Vergleich zum Archiv (Bauplan §5.6) — der Streifen
 *  erscheint von selbst, ohne Deploy am Wahlabend. */
export function NachWahlStreifen() {
  const [vorbei, setVorbei] = useState(false);
  useEffect(() => setVorbei(tageBis() <= 0), []);
  if (!vorbei) return null;
  return (
    <div className="border-b border-border bg-secondary px-4 py-2.5 text-center text-[13px] text-secondary-foreground">
      Die Wahl ist vorbei. Diese Seite dokumentiert den Stand der Programme vor dem 13.09.2026.
    </div>
  );
}
