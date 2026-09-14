import type { Metadata } from "next";

// Wie /wahlabend AUSSERHALB von app/(app)/: kein Konto-Gate, eigener Kopf,
// am Feature-Schalter `wahlabend`. Die Übersicht ist die dauerhafte Adresse —
// sie bleibt richtig, auch wenn gerade keine Wahl ansteht.
export const metadata: Metadata = {
  title: "Wahlen in Oldenburg | Ratslotse",
  description:
    "Alle Wahlen in Oldenburg auf einen Blick: die nächste mit Countdown, die gelaufenen mit ihrem Ergebnis — aus den Open-Data-Zahlen der Stadt.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Wahlen in Oldenburg",
    description: "Die nächste Wahl mit Countdown, die gelaufenen mit ihrem Ergebnis.",
  },
};

export default function WahlenLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
