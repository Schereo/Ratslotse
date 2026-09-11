import type { Metadata } from "next";

// /tipp lebt wie /wahlabend AUSSERHALB von app/(app)/: kein Konto-Gate,
// eigener Kopf. Anders als der Wahlabend hängt es an einem EIGENEN
// Feature-Schalter (`tippspiel`, kern/features.py) — die Seite soll auch
// nach dem Wahlabend noch als Rückblick laufen können, unabhängig davon,
// wann der Wahlabend-Schalter selbst wieder abgeschaltet wird.
export const metadata: Metadata = {
  title: "Tippspiel — Ratswahl Oldenburg 2026 | Ratslotse",
  description:
    "Wie geht die Ratswahl in Oldenburg aus? Tippe die Sitzverteilung und auf Wunsch die OB-Wahl. Ohne Konto mitmachen und am Wahlabend die Rangliste verfolgen.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Tippspiel — Ratswahl Oldenburg 2026",
    description: "Wie geht die Ratswahl aus? Verteile 52 Sitze auf 16 Wahllisten und mach ohne Konto mit.",
  },
};

export default function TippLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
