"use client";

// Die Beamer-Bühne: eine feste 1920×1080-Fläche, die auf jede Leinwand
// skaliert wird — so, wie das Artboard (1b/1g/1i) sie vorgibt („1920×1080,
// halbe Größe" heißt dort wörtlich `transform:scale(.5)`).
//
// Warum eine feste Fläche statt eines fließenden Layouts: Die drei Screens
// sind für GENAU einen Ort gebaut, die Leinwand im Raum. Ein fließendes
// Layout nimmt einem 1920-px-Beamer die Größenverhältnisse des Entwurfs
// (104-px-Titel, 74-px-Zeilen, 30-px-Punkte) und liefert stattdessen die
// Desktop-Variante einer Webseite — mittig, klein, viel Leerraum unten. Genau
// so sah es bis 11.09. aus („lieblos", Tim). Mit der Bühne stimmen die Maße
// auf 1080p, auf 4K und auf einem 1366er-Beamer gleichermaßen; nur der
// Maßstab ändert sich.
//
// Auf dem Handy (unter 900 px) zeigt `live.tsx` statt der Bühne eine
// kompakte Rangliste — eine auf 20 % verkleinerte Leinwand wäre unlesbar.

import { useEffect, useState } from "react";
import { BrandMark } from "@/components/brand";

export const BUEHNE_BREITE = 1920;
export const BUEHNE_HOEHE = 1080;

/** Der Maßstab, mit dem die 1920×1080-Fläche ins Fenster passt — `null`,
 *  solange noch nicht gemessen wurde (erstes Bild: nichts statt falsch). */
export function useBuehnenMassstab(): number | null {
  const [massstab, setMassstab] = useState<number | null>(null);
  useEffect(() => {
    const messen = () => setMassstab(Math.min(window.innerWidth / BUEHNE_BREITE, window.innerHeight / BUEHNE_HOEHE));
    messen();
    window.addEventListener("resize", messen);
    return () => window.removeEventListener("resize", messen);
  }, []);
  return massstab;
}

/** Ist das Fenster zu schmal für die Bühne (unter `lg`, 1024 px)? `null`,
 *  solange noch nicht gemessen — die Entscheidung fällt im Browser, nicht per
 *  CSS, damit nie beide Fassungen zugleich im Baum stehen (das verdoppelte
 *  Namen und Schilder für Screenreader und Tests). */
export function useSchmal(): boolean | null {
  const [schmal, setSchmal] = useState<boolean | null>(null);
  useEffect(() => {
    const messen = () => setSchmal(window.innerWidth < 1024);
    messen();
    window.addEventListener("resize", messen);
    return () => window.removeEventListener("resize", messen);
  }, []);
  return schmal;
}

export function Buehne({ children, className }: { children: React.ReactNode; className?: string }) {
  const massstab = useBuehnenMassstab();
  return (
    <div className="relative h-[100dvh] w-full overflow-hidden">
      {massstab !== null && (
        <div
          style={{
            width: BUEHNE_BREITE, height: BUEHNE_HOEHE,
            transform: `translate(-50%, -50%) scale(${massstab})`,
          }}
          className={`absolute left-1/2 top-1/2 origin-center ${className ?? ""}`}
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** Der Kopf aller drei Beamer-Screens: Marke links, Live-Zeile rechts. */
export function BeamerKopf({ untertitel, rechts }: { untertitel: string; rechts: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <BrandMarkGross />
        <span className="font-display text-[30px] font-bold">Ratslotse</span>
        <span className="border-l-2 border-border pl-4 text-[26px] text-muted-foreground">{untertitel}</span>
      </div>
      <div className="flex items-center gap-3.5 text-[26px] text-muted-foreground">{rechts}</div>
    </div>
  );
}

/** Der pulsierende Punkt mit „Live" bzw. „Endstand". */
export function LivePunkt({ endstand }: { endstand: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5 font-semibold text-signal">
      <span className="relative flex h-3.5 w-3.5">
        {!endstand && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal opacity-75 motion-reduce:hidden" />}
        <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-signal" />
      </span>
      {endstand ? "Endstand" : "Live"}
    </span>
  );
}

/** Zahl in deutscher Schreibweise, eine Nachkommastelle: 12,9. */
export function dezimal(n: number, stellen = 1): string {
  return n.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

function BrandMarkGross() {
  return <BrandMark className="h-11 w-11" />;
}
