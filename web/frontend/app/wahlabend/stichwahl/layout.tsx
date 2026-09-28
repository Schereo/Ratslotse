import type { Metadata } from "next";

// Eigene Metadaten, aber dieselbe Hülle wie /wahlabend (die kommt vom
// darüberliegenden Layout): kein Konto-Gate, eigener Kopf, Feature-Schalter
// `wahlabend`.
export const metadata: Metadata = {
  title: "OB-Stichwahl 2026 in Oldenburg: Ergebnis und Rückblick | Ratslotse",
  description:
    "Ergebnis der Oldenburger OB-Stichwahl vom 27. September 2026 mit Vergleich zum ersten Wahlgang, Wahlbezirken und Rückblick auf die Hochrechnung.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "OB-Stichwahl 2026 in Oldenburg: Ergebnis und Rückblick",
    description: "Ergebnis, Vergleich zum ersten Wahlgang und Rückblick auf die Hochrechnung.",
    // Das Bild zeigt den Stand von JETZT: Wer den Link am Abend in einen
    // Chat stellt, bekommt die Zahlen als Vorschau (Backend rendert es,
    // `runoff_image.py`). Relativ, `metadataBase` macht es absolut.
    images: [{ url: "/api/wahlabend/stichwahl/bild.png?format=quer", width: 1200, height: 630, alt: "Stand der OB-Stichwahl in Oldenburg" }],
  },
  twitter: { card: "summary_large_image" },
};

export default function StichwahlLayout({ children }: { children: React.ReactNode }) {
  return children;
}
