import type { Metadata } from "next";

// Seit 10/2026 IN der App-Hülle: Über „Analyse“ → „Wahlen“ kam man auf eine
// Seite ohne Seitenleiste und eigenem Kopf und glaubte sich nicht mehr in
// Ratslotse (Tims Befund 16.10.2026). Ohne Konto bleibt sie lesbar — sie steht
// in lib/public-routes.ts und bekommt dann die PublicShell. Am Feature-Schalter
// `wahlabend`. Die Übersicht ist die dauerhafte Adresse — sie bleibt richtig,
// auch wenn gerade keine Wahl ansteht.
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
  return children;
}
