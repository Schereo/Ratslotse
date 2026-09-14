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
  },
};

export default function StichwahlLayout({ children }: { children: React.ReactNode }) {
  return children;
}
