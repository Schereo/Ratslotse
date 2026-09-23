import type { Metadata } from "next";

// Eigene Metadaten, aber dieselbe Hülle wie /wahlabend (die kommt vom
// darüberliegenden Layout): kein Konto-Gate, eigener Kopf, Feature-Schalter
// `wahlabend`.
export const metadata: Metadata = {
  title: "Stichwahl zum Oberbürgermeisteramt — Oldenburg 2026 | Ratslotse",
  description:
    "Stichwahl um das Oberbürgermeisteramt in Oldenburg am 27. September 2026: Auszählungsstand und Ergebnis der beiden Bestplatzierten, live aus den Zahlen der Stadt.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Stichwahl zum Oberbürgermeisteramt — Oldenburg 2026",
    description: "Auszählungsstand und Ergebnis der Stichwahl, live aus den Zahlen der Stadt.",
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
