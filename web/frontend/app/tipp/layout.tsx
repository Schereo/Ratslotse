import type { Metadata } from "next";

// /tipp lebt wie /wahlabend AUSSERHALB von app/(app)/: kein Konto-Gate,
// eigener Kopf. Anders als der Wahlabend hängt es an einem EIGENEN
// Feature-Schalter (`tippspiel`, kern/features.py) — die Seite soll auch
// nach dem Wahlabend noch als Rückblick laufen können, unabhängig davon,
// wann der Wahlabend-Schalter selbst wieder abgeschaltet wird.
export const metadata: Metadata = {
  title: "Tippspiel — Ratswahl Oldenburg 2026 | Ratslotse",
  description:
    "Wer tippt den Rat am besten? 52 Sitze auf 16 Listen verteilen, optional die OB-Prozente — ohne Konto, per QR-Link. Live-Vergleich und Scoreboard am Wahlabend.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Tippspiel — Ratswahl Oldenburg 2026",
    description: "52 Sitze auf 16 Listen tippen — ohne Konto, per QR-Link.",
  },
};

export default function TippLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
